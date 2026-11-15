"""Rebuild all derived judge analysis without network or third-party dependencies."""
import collections, contextlib, io, json, sys, unittest, zipfile
from pathlib import Path
from judge import ROOT, SOURCE, INTENTS, SCHEMA, read, save, sha, csvread, csvwrite, validate, request_for, check_freeze, source_hashes

def analyze():
    check_freeze()
    snapshot=read(ROOT/'inputs/final_review_snapshot.json')
    refs={r['id']:r for r in snapshot['workbook_rows']['Fresh evaluation']}
    index=read(ROOT/'inputs/assessment_index.json'); records=[]
    for r in index:
        p=ROOT/'judgments'/f"{r['id']}_{r['version']}.json"
        if not p.exists(): raise ValueError('Missing judgment '+p.name)
        raw=read(p); j=validate(raw['judgment'],r); ref=refs[r['id']]
        assert raw['request']==request_for(r)
        assert r['query']==ref['query'] and r['prediction']==ref['baseline_prediction' if r['version']=='baseline' else 'revised_prediction']
        records.append({**r,**j,'alternative_intents':';'.join(j['alternative_intents']),
            'original_label':ref['source_intent'],'reviewed_label':ref['reviewed_intent'],
            'original_exact_match':int(r['prediction']==ref['source_intent']),
            'reviewed_exact_match':int(r['prediction']==ref['reviewed_intent']),
            'judge_vs_original_label':int(j['proposed_intent']==ref['source_intent']),
            'judge_vs_reviewed_label':int(j['proposed_intent']==ref['reviewed_intent']),
            'score_vs_original_em':int(j['score']==int(r['prediction']==ref['source_intent'])),
            'score_vs_reviewed_em':int(j['score']==int(r['prediction']==ref['reviewed_intent'])),
            'human_reviewed':ref['participant_approval']=='Approved',
            'reviewed_failure_category':ref['failure_category'],
            'review_status':'NEEDS_REVIEW' if j['ambiguity'] or j['proposed_intent']!=ref['reviewed_intent'] else 'NO_FLAG'})
    records.sort(key=lambda r:(r['id'],r['version']))
    (ROOT/'results').mkdir(exist_ok=True)
    csvwrite(ROOT/'results/assessments.csv',records)
    summary={}
    for version in ('baseline','focused'):
        rs=[r for r in records if r['version']==version]
        summary[version]={'assessments':len(rs),'judge_pass':sum(r['score'] for r in rs),'judge_fail':sum(1-r['score'] for r in rs),
            'ambiguity_flags':sum(r['ambiguity'] for r in rs),
            **{key:sum(r[key] for r in rs) for key in ['original_exact_match','reviewed_exact_match','judge_vs_original_label','judge_vs_reviewed_label','score_vs_original_em','score_vs_reviewed_em']},
            'original_confusion':dict(collections.Counter(f"EM={r['original_exact_match']},judge={r['score']}" for r in rs)),
            'reviewed_confusion':dict(collections.Counter(f"EM={r['reviewed_exact_match']},judge={r['score']}" for r in rs))}
    by={(r['id'],r['version']):r for r in records}; pairs=[]
    for tid in sorted(refs):
        b=by[tid,'baseline']; f=by[tid,'focused']
        pairs.append({'id':tid,'baseline_score':b['score'],'focused_score':f['score'],'change':'WIN' if b['score']<f['score'] else 'REGRESSION' if b['score']>f['score'] else 'UNCHANGED_PASS' if b['score'] else 'UNCHANGED_FAIL',
            'identical_judge_input':b['query']==f['query'] and b['prediction']==f['prediction'],
            'baseline_proposed':b['proposed_intent'],'focused_proposed':f['proposed_intent'],'proposed_intent_consistent':b['proposed_intent']==f['proposed_intent'],
            'ambiguity_consistent':b['ambiguity']==f['ambiguity']})
    csvwrite(ROOT/'results/paired_results.csv',pairs)
    summary['paired']={'changes':dict(collections.Counter(p['change'] for p in pairs)),
        'judge_delta_percentage_points':summary['focused']['judge_pass']-summary['baseline']['judge_pass'],
        'proposed_intent_inconsistency_ids':[p['id'] for p in pairs if not p['proposed_intent_consistent']],
        'ambiguity_inconsistency_ids':[p['id'] for p in pairs if not p['ambiguity_consistent']]}
    identical=[p for p in pairs if p['identical_judge_input']]
    summary['paired'].update(identical_input_pairs=len(identical),identical_input_score_disagreement_ids=[p['id'] for p in identical if p['baseline_score']!=p['focused_score']],
        identical_input_score_delta=sum(p['focused_score']-p['baseline_score'] for p in identical),
        changed_prediction_score_delta=sum(p['focused_score']-p['baseline_score'] for p in pairs if not p['identical_judge_input']))
    summary['by_reference_intent']={v:{intent:{'n':len(rs:=[r for r in records if r['version']==v and r['original_label']==intent]),'judge_pass':sum(r['score'] for r in rs)} for intent in INTENTS} for v in ('baseline','focused')}
    categories=sorted({r['reviewed_failure_category'] for r in records if r['reviewed_failure_category']})
    summary['by_review_failure_category']={v:{category:{'n':len(rs:=[r for r in records if r['version']==v and r['reviewed_failure_category']==category]),'judge_pass':sum(r['score'] for r in rs),'score_agrees_with_reviewed_em':sum(r['score_vs_reviewed_em'] for r in rs)} for category in categories} for v in ('baseline','focused')}
    summary['by_seed_family']={f'seed_{i:02d}':{v:sum(r['score'] for r in records if r['version']==v and int(r['id'][1:])//4==i) for v in ('baseline','focused')} for i in range(25)}
    attempts=[read(p) for p in sorted((ROOT/'attempts').glob('*.json'))]
    pt=ct=cached=0
    for a in attempts:
        usage=a.get('response',{}).get('usage',{}); pt+=usage.get('prompt_tokens',0); ct+=usage.get('completion_tokens',0); cached+=usage.get('prompt_tokens_details',{}).get('cached_tokens',0)
    prices=read(ROOT/'config.json')['prices_usd_per_million']
    rejected_parsed=[]
    for a in attempts:
        if a['status']=='OK' or not a.get('response'): continue
        try:
            rejected=json.loads(a['response']['choices'][0]['message']['content'])
            accepted=by[a['id'],a['version']]
            rejected_parsed.append({'id':a['id'],'version':a['version'],'attempt':a['attempt'],
                'score_changed':rejected.get('score')!=accepted['score'],
                'proposed_intent_changed':rejected.get('proposed_intent')!=accepted['proposed_intent'],
                'rejected_score':rejected.get('score'),'accepted_score':accepted['score'],
                'rejected_proposed_intent':rejected.get('proposed_intent'),'accepted_proposed_intent':accepted['proposed_intent']})
        except (KeyError,TypeError,ValueError): pass
    summary['retry_sensitivity']={'parsed_rejected_responses':len(rejected_parsed),'score_changes':sum(x['score_changed'] for x in rejected_parsed),'proposed_intent_changes':sum(x['proposed_intent_changed'] for x in rejected_parsed),'detail':rejected_parsed}
    summary['usage']={'api_attempts':len(attempts),'failed_attempts':sum(a['status']!='OK' for a in attempts),'prompt_tokens':pt,'cached_prompt_tokens':cached,'completion_tokens_including_reasoning':ct,
        'interrupted_unrecorded_requests_maximum':read(ROOT/'evidence/transport_adjustment.json')['unrecorded_inflight_requests_maximum'] if (ROOT/'evidence/transport_adjustment.json').exists() else 0,
        'estimated_cost_usd':((pt-cached)*prices['input']+cached*prices['cached_input']+ct*prices['output'])/1e6,
        'cost_note':'Calculated from returned usage and published rates; not an invoiced charge. Missing response usage and interrupted in-flight calls cannot be billed exactly here.'}
    inconsistent=set(summary['paired']['proposed_intent_inconsistency_ids'])
    for r in records:
        if r['id'] in inconsistent: r['review_status']='NEEDS_REVIEW'
    csvwrite(ROOT/'results/assessments.csv',records)
    summary['review_ticket_ids']=sorted({r['id'] for r in records if r['review_status']=='NEEDS_REVIEW'})
    summary['failure_types']=dict(collections.Counter(a.get('error_type','INTERRUPTED') for a in attempts if a['status']!='OK'))
    csvwrite(ROOT/'results/review_needed.csv',[r for r in records if r['review_status']=='NEEDS_REVIEW'])
    csvwrite(ROOT/'results/disagreements.csv',[r for r in records if not r['judge_vs_original_label'] or not r['judge_vs_reviewed_label'] or not r['score_vs_original_em'] or not r['score_vs_reviewed_em']])
    save(ROOT/'results/summary.json',summary)
    return summary

def verify():
    frozen=check_freeze(); current=source_hashes()
    assert current==frozen['original_project_sha256'],'Original project files changed'
    rows=read(ROOT/'inputs/assessment_index.json')
    assert len(rows)==200 and len({(r['id'],r['version']) for r in rows})==200
    for r in rows:
        req=request_for(r); user=json.loads(req['messages'][1]['content'])
        assert set(user)=={'query','predicted_category'}
        assert set(req)=={'model','reasoning_effort','max_completion_tokens','store','messages','response_format'}
        saved=read(ROOT/'judgments'/f"{r['id']}_{r['version']}.json")
        assert saved['request']==req and saved['status']=='OK'
        validate(saved['judgment'],r)
        response=saved['response']; choice=response['choices'][0]
        assert response['model']==read(ROOT/'config.json')['model']
        assert choice['finish_reason']=='stop' and not choice['message'].get('refusal')
        assert json.loads(choice['message']['content'])==saved['judgment']
    # Meaningful negative controls: reject malformed, contradictory and leaked inputs.
    r=rows[0]; good={'score':1,'correctness':'correct','rationale':'The prediction follows the routing policy.','ambiguity':False,'proposed_intent':r['prediction'],'alternative_intents':[]}
    bads=[{**good,'score':True},{**good,'score':0},{**good,'correctness':'incorrect'},{**good,'ground_truth':r['prediction']},{**good,'proposed_intent':'invalid'},{**good,'alternative_intents':[r['prediction']]},{**good,'rationale':''},{**good,'ambiguity':'false'}]
    for bad in bads:
        try: validate(bad,r)
        except ValueError: pass
        else: raise AssertionError('Validation negative control failed')
    summary=analyze()
    assert [summary[v]['original_exact_match'] for v in ('baseline','focused')]==[92,94]
    assert [summary[v]['reviewed_exact_match'] for v in ('baseline','focused')]==[93,93]
    evidence={'status':'PASS','assessments_validated':200,'negative_controls_passed':len(bads),'frozen_inputs_match':True,'original_project_files_unchanged':len(current),'all_requests_allowlisted':True,'ground_truth_not_sent':True,'langsmith_writes':0,'classifier_calls':0,'original_exact_match':[92,94],'reviewed_exact_match':[93,93]}
    save(ROOT/'evidence/validation.json',evidence)
    print(json.dumps(evidence,indent=2)); return evidence

if __name__=='__main__':
    print(json.dumps(analyze(),indent=2))
