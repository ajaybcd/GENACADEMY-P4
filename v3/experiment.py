"""Isolated v3 refund-policy experiment. Never edits historical project evidence."""
import argparse, concurrent.futures, csv, hashlib, json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'customer-support'
if not SOURCE.exists(): SOURCE=ROOT.parent  # GitHub layout keeps the main project at repository root.
INTENTS=('order_status','refund_request','product_issue','account_help','other')
ADDITION='''Refund-processing exceptions: If the customer has already returned an item and is waiting for refund money, choose refund_request. A missing, delayed, or not-yet-received refund payment on a card is a refund-processing issue, not a missing delivery. If the customer asks to cancel an unwanted order and receive a refund because they no longer need it, choose refund_request unless an actual non-delivery or delivered-product problem is stated. Mentioning an order number, waiting, a card, or a refund does not by itself establish an order_status issue. Apply the underlying-problem precedence above only when the query actually describes an order that was not delivered or a delivered item that is damaged, wrong, defective, or not as described.'''
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def write_csv(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def prepare():
    if (ROOT/'inputs/freeze.json').exists():return read(ROOT/'inputs/freeze.json')
    snapshot=read(SOURCE/'outputs/final_review_snapshot.json')
    rows=snapshot['workbook_rows']['Fresh evaluation']
    assert len(rows)==100 and len({r['id'] for r in rows})==100
    data=[]
    for row in rows:
        new='product_issue' if row['id']=='t046' else row['reviewed_intent']
        assert new in INTENTS
        data.append({'id':row['id'],'query':row['query'],'historical_reviewed_intent':row['reviewed_intent'],
          'v3_policy_intent':new,'baseline_prediction':row['baseline_prediction'],'focused_prediction':row['revised_prediction'],
          'source_workbook_row':row['row'],'label_changed':row['reviewed_intent']!=new})
    assert [r['id'] for r in data if r['label_changed']]==['t046']
    focused=(SOURCE/'prompts/focused.txt').read_text(encoding='utf-8').rstrip()
    prompt=focused+'\n\n'+ADDITION
    (ROOT/'prompts').mkdir(parents=True,exist_ok=True)
    (ROOT/'prompts/v3.txt').write_text(prompt+'\n',encoding='utf-8')
    protected=[SOURCE/'outputs/customer_support_evaluation.xlsx',SOURCE/'outputs/final_review_snapshot.json',*list((SOURCE/'live_runs').glob('*')),*list((SOURCE/'prompts').glob('*')),*list((SOURCE/'outputs/langsmith_annotation_sync').glob('*'))]
    freeze={'prepared_utc':utc(),'model':'gpt-4o-mini','temperature':0,'tickets':100,
       'source_hashes':{str(p.relative_to(SOURCE)):sha(p) for p in protected if p.is_file()},
       'v3_prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
       'policy_approval':'User explicitly approved product_issue for damaged products and v3 clarified refund rules in this conversation.',
       'label_changes':[{'id':'t046','old':'refund_request','new':'product_issue','reason':'Consistent damaged-product routing, explicitly approved by user.'}],
       'comparison_note':'Historical baseline and focused predictions are rescored under the same v3 policy labels. Only v3 makes new classifier calls. Calls occur on a later date; prompt effect is not isolated from service variability.'}
    save(ROOT/'inputs/tickets.json',data);save(ROOT/'inputs/freeze.json',freeze)
    write_csv(ROOT/'inputs/labels_v3_policy.csv',[{'id':r['id'],'query':r['query'],'historical_reviewed_intent':r['historical_reviewed_intent'],'v3_policy_intent':r['v3_policy_intent'],'label_changed':r['label_changed']} for r in data])
    print('Prepared 100 fixed tickets; one approved label change (t046); saved v3 prompt.',flush=True)
    return freeze

def payload(query):
    prompt=(ROOT/'prompts/v3.txt').read_text(encoding='utf-8').rstrip()
    return {'model':'gpt-4o-mini','temperature':0,'messages':[{'role':'system','content':prompt},{'role':'user','content':query}],
      'response_format':{'type':'json_schema','json_schema':{'name':'intent_classification','strict':True,'schema':{'type':'object','properties':{'intent':{'type':'string','enum':list(INTENTS)}},'required':['intent'],'additionalProperties':False}}}}
def accepted(path,row):
    x=read(path)
    assert x['id']==row['id'] and x['request']==payload(row['query'])
    assert x['prediction'] in INTENTS and x['status']=='OK'
    return x
def assess(row,direct):
    path=ROOT/'runs'/f"{row['id']}.json"
    if path.exists():return accepted(path,row)
    request=payload(row['query'])
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    existing=list((ROOT/'attempts').glob(row['id']+'_*.json'))
    offset=max([int(p.stem.rsplit('_',1)[1]) for p in existing],default=0)
    for k in range(1,4):
        attempt=offset+k; started=utc()
        record={'id':row['id'],'attempt':attempt,'started_utc':started,'request':request}
        try:
            req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(request).encode(),headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY'],'Content-Type':'application/json'})
            with opener.open(req,timeout=45) as response:answer=json.load(response)
            record['response']=answer;choice=answer['choices'][0]
            if choice.get('finish_reason')!='stop' or choice['message'].get('refusal'):raise ValueError('Incomplete or refused classification')
            out=json.loads(choice['message']['content'])
            if set(out)!={'intent'} or out['intent'] not in INTENTS:raise ValueError('Invalid structured intent')
            record.update(status='OK',prediction=out['intent'],ended_utc=utc())
            save(ROOT/'attempts'/f"{row['id']}_{attempt}.json",record);save(path,record)
            return record
        except Exception as e:
            record.update(status='ERROR',error_type=type(e).__name__,http_status=getattr(e,'code',None),ended_utc=utc())
            save(ROOT/'attempts'/f"{row['id']}_{attempt}.json",record)
            if getattr(e,'code',None) in [400,401,403,404]:break
            if k<3:time.sleep(k*2)
    raise RuntimeError('Classification unavailable for '+row['id'])

def run(direct=False):
    prepare()
    if not os.environ.get('OPENAI_API_KEY'):raise RuntimeError('Saved OpenAI credential was not loaded')
    rows=read(ROOT/'inputs/tickets.json')
    (ROOT/'runs').mkdir(exist_ok=True);(ROOT/'attempts').mkdir(exist_ok=True)
    # First target case is a real retained assessment, not an extra billed probe.
    assess(next(r for r in rows if r['id']=='t024'),direct)
    print('First saved v3 classification validated; running remaining tickets.',flush=True)
    errors=[];done=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        future={pool.submit(assess,row,direct):row['id'] for row in rows}
        for f in concurrent.futures.as_completed(future):
            try:f.result()
            except Exception:errors.append(future[f])
            done+=1
            if done%10==0:print(f'v3: {done}/100 processed; {len(errors)} unresolved',flush=True)
    if errors:
        save(ROOT/'results/incomplete_run.json',{'unresolved_ids':errors,'checked_utc':utc()})
        raise RuntimeError('Some v3 calls are unresolved; resume the same run without replacing saved outputs')
    analyze()

def analyze():
    freeze=prepare();rows=read(ROOT/'inputs/tickets.json');result=[]
    for row in rows:
        raw=accepted(ROOT/'runs'/f"{row['id']}.json",row);v3=raw['prediction'];ref=row['v3_policy_intent']
        b=int(row['baseline_prediction']==ref);f=int(row['focused_prediction']==ref);v=int(v3==ref)
        change='FIXED' if v>f else 'REGRESSION' if v<f else 'STILL_PASS' if v else 'STILL_FAIL'
        result.append({**row,'v3_prediction':v3,'baseline_exact_match':b,'focused_exact_match':f,'v3_exact_match':v,'v3_vs_focused':change,
          'prediction_changed':v3!=row['focused_prediction'],
          'action':'Review v3 failure' if not v else 'Approved reference policy applied; historical label retained' if row['label_changed'] else 'New model prediction — review change' if v3!=row['focused_prediction'] else 'No change needed'})
    attempts=[read(p) for p in (ROOT/'attempts').glob('*.json')]
    totals={v:sum(r[v+'_exact_match'] for r in result) for v in ['baseline','focused','v3']}
    protected=all(sha(SOURCE/name)==h for name,h in freeze['source_hashes'].items());assert protected
    summary={'completed_utc':utc(),'tickets':100,'completed':100,'errors':0,'model_requested':'gpt-4o-mini','temperature':0,
       'returned_models':sorted({read(p)['response']['model'] for p in (ROOT/'runs').glob('*.json')}),
       'historical_reviewed_label_scores':{'baseline':93,'focused':93},'same_v3_policy_scores':totals,
       'label_policy_effect_before_new_calls':{'baseline':totals['baseline']-93,'focused':totals['focused']-93},
       'v3_gain_vs_focused_percentage_points':totals['v3']-totals['focused'],
       'v3_paired_changes':{c:sum(r['v3_vs_focused']==c for r in result) for c in ['FIXED','REGRESSION','STILL_PASS','STILL_FAIL']},
       'changed_prediction_ids':[r['id'] for r in result if r['prediction_changed']],
       'remaining_failed_ids':[r['id'] for r in result if not r['v3_exact_match']],
       'approved_label_changes':freeze['label_changes'],'historical_artifacts_unchanged':protected,
       'recorded_api_attempts':len(attempts),'failed_attempts':sum(r['status']!='OK' for r in attempts),
       'usage':{'prompt_tokens':sum(r.get('response',{}).get('usage',{}).get('prompt_tokens',0) for r in attempts),'completion_tokens':sum(r.get('response',{}).get('usage',{}).get('completion_tokens',0) for r in attempts)},
       'scope':'Same known 100 synthetic tickets, 25 related seed families; no independent test or v3 LLM judge run. Historical scores use saved predictions, not simultaneous control reruns.'}
    save(ROOT/'results/comparison.json',summary);save(ROOT/'results/ticket_comparison.json',result);write_csv(ROOT/'results/ticket_comparison.csv',result)
    if summary['remaining_failed_ids']:write_csv(ROOT/'results/remaining_failures.csv',[r for r in result if not r['v3_exact_match']])
    print(json.dumps(summary,indent=2),flush=True)
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','run','analyze']);ap.add_argument('--direct-network',action='store_true');args=ap.parse_args()
    try:{'prepare':prepare,'run':lambda:run(args.direct_network),'analyze':analyze}[args.action]()
    except Exception as e:print(json.dumps({'status':'ERROR','error_type':type(e).__name__,'message':str(e) if isinstance(e,(RuntimeError,AssertionError)) else 'Inspect local attempt records.'}),flush=True);raise SystemExit(1)
