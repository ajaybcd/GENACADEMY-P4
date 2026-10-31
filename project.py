"""Customer-support evaluation: saved-run analysis and credential-gated live runs."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
INTENTS = ('order_status', 'refund_request', 'product_issue', 'account_help', 'other')
SOURCE_COMMIT = 'ef517b274cf86a2c4fa8ae72fdc89b3dce80f41d'
BASELINE = """You are a triage system for an e-commerce support inbox.
Classify the customer's ticket into EXACTLY ONE of these categories:
- order_status: questions about where an order is, tracking, delivery ETA
- refund_request: the customer wants their money back
- product_issue: the item arrived broken, wrong, defective, or not as described
- account_help: login, password, address, payment method changes
- other: anything that doesn't fit the above (general questions, feedback, browsing)
Return only the intent key."""
FOCUSED_ADDITION = """Routing precedence: classify the underlying problem before the requested remedy. When a refund is requested because an order never arrived, choose order_status; when it is requested because an item arrived damaged, wrong, defective, or not as described, choose product_issue. Otherwise keep the category definitions above unchanged."""


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, columns=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exact_match(outputs, reference_outputs):
    prediction = outputs.get('intent')
    reference = reference_outputs.get('intent')
    if prediction not in INTENTS or reference not in INTENTS:
        raise ValueError('Exact Match requires valid intent strings on both sides.')
    return {'key': 'intent_exact_match', 'score': int(prediction == reference)}


def validated_runs():
    baseline = read_csv(ROOT / 'source/results_v1.csv')
    revised = read_csv(ROOT / 'source/results_v2.csv')
    if len(baseline) != 100 or len(revised) != 100:
        raise ValueError('Expected 100 tickets in both saved runs.')
    right = {r['id']: r for r in revised}
    if len(right) != 100 or len({r['id'] for r in baseline}) != 100:
        raise ValueError('Duplicate ticket IDs.')
    if set(right) != {r['id'] for r in baseline}:
        raise ValueError('Run ID sets differ.')
    for row in baseline:
        other = right[row['id']]
        if any(row[k] != other[k] for k in ('ticket_text', 'true_category')):
            raise ValueError('Query or reference changed for ' + row['id'])
        for record in (row, other):
            result = exact_match({'intent': record['predicted_category']}, {'intent': record['true_category']})
            if (record['correct'].lower() == 'true') != bool(result['score']):
                raise ValueError('Stored correctness disagrees with Exact Match.')
    return baseline, right


def observation(row):
    """Case notes written before grouping mechanisms. No claim of human review."""
    n = int(row['id'][1:])
    if 4 <= n <= 7:
        return 'The customer requests money back after non-delivery. The prediction follows the remedy; the supplied routing policy assigns non-delivery to order_status.'
    if 44 <= n <= 47:
        return 'The ticket describes a damaged or broken laptop and requests a refund. The prediction follows the refund request; the supplied routing policy assigns the damaged item to product_issue.'
    if n == 16:
        return 'The spinning link is specifically an order-tracking link. No login or checkout problem is stated, so the supplied order_status label remains appropriate.'
    if n in (94, 95):
        return 'The customer asks whether a student discount exists. Mentioning checkout or an order number does not establish an account or authentication problem.'
    return ''


def failure_group(ticket_id):
    n = int(ticket_id[1:])
    if 4 <= n <= 7 or 44 <= n <= 47:
        return 'Requested remedy overrides underlying problem'
    if n == 16 or n in (94, 95):
        return 'Technical context mistaken for account problem'
    return ''


def analyze():
    baseline, revised = validated_runs()
    output = ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    dataset = [{'query': r['ticket_text'], 'intent': r['true_category'], 'id': r['id']} for r in baseline]
    write_csv(output / 'langsmith_dataset.csv', dataset, ['query', 'intent', 'id'])
    # Save observations before defining/assigning the taxonomy.
    notes = [{'id': r['id'], 'query': r['ticket_text'], 'reference_intent': r['true_category'],
              'prediction': r['predicted_category'], 'observation': observation(r),
              'review_origin': 'AI-assisted draft', 'participant_review': 'PENDING'}
             for r in baseline if r['predicted_category'] != r['true_category']]
    write_csv(output / 'failure_notes_before_categories.csv', notes)
    categories = [
        {'category': 'Requested remedy overrides underlying problem', 'definition': 'A refund remedy takes precedence over the stated delivery or damaged-product problem.', 'baseline_count': 8, 'upstream_revised_count': 0, 'examples': 't004-t007; t044-t047', 'proposed_fix': FOCUSED_ADDITION},
        {'category': 'Technical context mistaken for account problem', 'definition': 'Tracking-link or discount context is routed to account_help without an account, login, or checkout-blocking issue.', 'baseline_count': 0, 'upstream_revised_count': 3, 'examples': 't016; t094; t095', 'proposed_fix': 'Keep tracking failures with order_status and discount availability with other; require actual account or checkout failure for account_help.'},
    ]
    write_csv(output / 'failure_categories.csv', categories)
    review = []
    for row in baseline:
        new = revised[row['id']]
        old_ok = row['predicted_category'] == row['true_category']
        new_ok = new['predicted_category'] == new['true_category']
        change = 'WIN' if not old_ok and new_ok else 'REGRESSION' if old_ok and not new_ok else 'STILL_PASS' if new_ok else 'STILL_FAIL'
        review.append({'id': row['id'], 'query': row['ticket_text'], 'source_intent': row['true_category'],
                       'reviewed_intent': row['true_category'], 'label_review': 'AI draft retained; participant approval pending',
                       'baseline_prediction': row['predicted_category'], 'baseline_exact_match': int(old_ok),
                       'upstream_revised_prediction': new['predicted_category'], 'upstream_revised_exact_match': int(new_ok),
                       'change': change, 'failure_category': failure_group(row['id']) if not old_ok or not new_ok else '',
                       'review_note': observation(row), 'participant_approved': '', 'participant_notes': ''})
    write_csv(output / 'evaluation_review.csv', review)
    write_csv(output / 'regression_results.csv', [r for r in review if r['change'] != 'STILL_PASS'] + [review[0]])
    write_csv(output / 'regression_requests.csv', [r for r in dataset if r['id'] in {n['id'] for n in notes} | {'t000','t016','t094','t095'}], ['query','intent','id'])
    summary = {'provenance': 'Recomputed from repository saved predictions; no fresh model or LangSmith run',
               'source_commit': SOURCE_COMMIT, 'tickets': len(review), 'baseline_correct': sum(r['baseline_exact_match'] for r in review),
               'upstream_revised_correct': sum(r['upstream_revised_exact_match'] for r in review),
               'wins': sum(r['change'] == 'WIN' for r in review), 'regressions': sum(r['change'] == 'REGRESSION' for r in review),
               'still_pass': sum(r['change'] == 'STILL_PASS' for r in review), 'still_fail': sum(r['change'] == 'STILL_FAIL' for r in review),
               'focused_prompt_status': 'PREPARED_NOT_RUN', 'participant_review_status': 'PENDING',
               'langsmith_evidence_status': 'PENDING', 'loom_status': 'SCRIPT_PREPARED_RECORDING_PENDING'}
    live_evidence=ROOT/'live_runs/langsmith_evidence.json'
    if live_evidence.exists():
        live=json.loads(live_evidence.read_text(encoding='utf-8'))
        summary.update(focused_prompt_status='COMPLETED',langsmith_evidence_status='COMPLETED',fresh_comparison=live.get('comparison',{}))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'source').iterdir() if p.is_file()}
    (output/'source_manifest.json').write_text(json.dumps({'repository':'The-Gen-Academy/4A-Customer-Support-Agent-Evaluation','commit':SOURCE_COMMIT,'sha256':hashes},indent=2)+'\n',encoding='utf-8')
    prompts = ROOT / 'prompts'
    prompts.mkdir(exist_ok=True)
    (prompts/'baseline.txt').write_text(BASELINE+'\n',encoding='utf-8')
    (prompts/'focused.txt').write_text(BASELINE+'\n\n'+FOCUSED_ADDITION+'\n',encoding='utf-8')
    return summary


def build_request(query, version='baseline'):
    if version not in ('baseline', 'focused'):
        raise ValueError('Unknown prompt version.')
    return {'model':'gpt-4o-mini', 'temperature':0, 'messages':[
        {'role':'system','content':BASELINE + ('\n\n'+FOCUSED_ADDITION if version == 'focused' else '')},
        {'role':'user','content':query}],
        'response_format':{'type':'json_schema','json_schema':{'name':'intent_classification','strict':True,
        'schema':{'type':'object','properties':{'intent':{'type':'string','enum':list(INTENTS)}},'required':['intent'],'additionalProperties':False}}}}


def classify(query, version):
    key = os.environ.get('OPENAI_API_KEY','').strip()
    if not key:
        raise RuntimeError('Set OPENAI_API_KEY locally before a live run.')
    request = urllib.request.Request('https://api.openai.com/v1/chat/completions',
        data=json.dumps(build_request(query,version)).encode(), headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'OpenAI HTTP {error.code}') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('OpenAI request failed or timed out.') from None
    choice = answer['choices'][0]
    if choice.get('finish_reason') != 'stop' or choice['message'].get('refusal'):
        raise ValueError('Model did not return a complete classification.')
    result = json.loads(choice['message']['content'])
    if set(result) != {'intent'} or result['intent'] not in INTENTS:
        raise ValueError('Invalid structured intent output.')
    return result


def live(version, destination):
    rows = read_csv(ROOT/'outputs/langsmith_dataset.csv')
    destination = Path(destination).resolve()
    if not destination.is_relative_to(ROOT):
        raise ValueError('Live artifacts must stay inside this project under p4.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive reservation prevents overwriting a saved run.
    with destination.open('x',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=['id','query','reference_intent','prediction','intent_exact_match','run_status','error'])
        writer.writeheader()
        for row in rows:
            record = {'id':row['id'],'query':row['query'],'reference_intent':row['intent'],'prediction':'','intent_exact_match':'','run_status':'ERROR','error':''}
            try:
                out = classify(row['query'],version)
                record.update(prediction=out['intent'],intent_exact_match=exact_match(out,{'intent':row['intent']})['score'],run_status='OK')
            except Exception as error:
                record['error'] = str(error)
            writer.writerow(record)
            stream.flush()
    records = read_csv(destination)
    completed = [r for r in records if r['run_status']=='OK']
    report = {'total':len(records),'completed':len(completed),'errors':len(records)-len(completed),
              'correct':sum(int(r['intent_exact_match']) for r in completed),'prompt_version':version,
              'prompt_sha256':hashlib.sha256(build_request('',version)['messages'][0]['content'].encode()).hexdigest()}
    destination.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if report['errors']:
        raise RuntimeError('Live run contains errors. Inspect saved records; errors are not quality FAILs.')
    return report


def langsmith_run(dataset_name, prefix):
    if not all(os.getenv(k,'').strip() for k in ('OPENAI_API_KEY','LANGSMITH_API_KEY')):
        raise RuntimeError('Set OPENAI_API_KEY and LANGSMITH_API_KEY locally.')
    from langsmith import Client
    client = Client()
    # Deliberately create a new dataset; never mutate a matching existing dataset.
    dataset = client.create_dataset(dataset_name=dataset_name, description='100 fixed repository tickets; query input, intent reference, id metadata. Repository routing policy retained pending participant review.')
    rows = read_csv(ROOT/'outputs/langsmith_dataset.csv')
    client.create_examples(dataset_id=dataset.id, examples=[{'inputs':{'query':r['query']},'outputs':{'intent':r['intent']},'metadata':{'id':r['id']}} for r in rows])
    experiment_names = []
    export_paths = []
    for version in ('baseline','focused'):
        def predict(inputs, selected=version):
            return classify(inputs['query'],selected)
        results = client.evaluate(predict,data=dataset_name,evaluators=[exact_match],experiment_prefix=prefix+'-'+version,
            metadata={'prompt_version':version,'model':'gpt-4o-mini','temperature':0,'source_commit':SOURCE_COMMIT},max_concurrency=2)
        records=[]
        for item in results:
            run=item['run']; example=item['example']
            records.append({'id':example.metadata.get('id',''),'query':example.inputs['query'],
                'reference_intent':example.outputs['intent'],'prediction':(run.outputs or {}).get('intent',''),
                'run_id':str(run.id),'error':run.error or ''})
        name=results.experiment_name
        export_path=ROOT/'live_runs'/f'{name}.csv'
        write_csv(export_path,records)
        export_paths.append(export_path)
        experiment_names.append(name)
    comparison=compare_live(export_paths[0],export_paths[1])
    evidence={'dataset_name':dataset_name,'dataset_id':str(dataset.id),'experiments':experiment_names,
        'note':'Open the dataset Experiments view and select both experiments for Comparison. Save its actual URL/screenshots after review.'}
    (ROOT/'live_runs/langsmith_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    evidence['comparison']=comparison
    (ROOT/'live_runs/langsmith_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    return evidence


def compare_live(baseline_path, focused_path):
    first=read_csv(baseline_path); second=read_csv(focused_path)
    index={r['id']:r for r in second}
    if len(index)!=len(second) or len({r['id'] for r in first})!=len(first) or set(index)!={r['id'] for r in first}:
        raise ValueError('Live runs need unique matching IDs.')
    comparison=[]
    for row in first:
        revised=index[row['id']]
        if any(row[k]!=revised[k] for k in ('query','reference_intent')):
            raise ValueError('Live run queries or references differ.')
        valid=all(not r.get('error') and r['prediction'] in INTENTS for r in (row,revised))
        old=row['prediction']==row['reference_intent']; new=revised['prediction']==revised['reference_intent']
        change='UNRESOLVED' if not valid else 'WIN' if not old and new else 'REGRESSION' if old and not new else 'STILL_PASS' if new else 'STILL_FAIL'
        comparison.append({'id':row['id'],'query':row['query'],'reference_intent':row['reference_intent'],
            'baseline_prediction':row['prediction'],'focused_prediction':revised['prediction'],'change':change})
    complete=[r for r in comparison if r['change']!='UNRESOLVED']
    old_count=sum(r['baseline_prediction']==r['reference_intent'] for r in complete)
    new_count=sum(r['focused_prediction']==r['reference_intent'] for r in complete)
    report={'total':len(comparison),'paired_completed':len(complete),'unresolved':len(comparison)-len(complete),
        'baseline_correct_paired':old_count,'focused_correct_paired':new_count,
        'accuracy_delta_percentage_points':100*(new_count-old_count)/len(complete) if complete else None,
        'wins':sum(r['change']=='WIN' for r in comparison),'regressions':sum(r['change']=='REGRESSION' for r in comparison)}
    # A comparison export is regenerated; classifier-run exports remain immutable.
    write_csv(ROOT/'live_runs/comparison.csv',comparison)
    (ROOT/'live_runs/comparison.summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('analyze')
    runner=sub.add_parser('live'); runner.add_argument('--version',choices=['baseline','focused'],required=True); runner.add_argument('--output',required=True)
    smith=sub.add_parser('langsmith'); smith.add_argument('--dataset',required=True); smith.add_argument('--prefix',default='week4-p4')
    compare=sub.add_parser('compare'); compare.add_argument('--baseline',required=True); compare.add_argument('--focused',required=True)
    args=parser.parse_args()
    if args.command=='analyze': result=analyze()
    elif args.command=='live':
        if not os.getenv('OPENAI_API_KEY','').strip(): parser.error('Set OPENAI_API_KEY locally before a live run.')
        result=live(args.version,args.output)
    elif args.command=='compare': result=compare_live(args.baseline,args.focused)
    else: result=langsmith_run(args.dataset,args.prefix)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
