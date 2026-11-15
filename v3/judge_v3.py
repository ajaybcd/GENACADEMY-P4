"""New judge assessments for saved v3 predictions; historical judgments untouched."""
import concurrent.futures, csv, hashlib, importlib.util, json, os, random, shutil, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from experiment import ROOT, read, save, sha

OUT=ROOT/'llm_judge';OLD=ROOT.parent/'llm-judge'
spec=importlib.util.spec_from_file_location('original_judge_validation',OLD/'judge.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
def utc():return datetime.now(timezone.utc).isoformat()
def prepare():
    OUT.mkdir(exist_ok=True)
    freeze=OUT/'freeze.json'
    if not freeze.exists():
        for name in ['rubric.txt','schema.json','config.json']:shutil.copyfile(OLD/name,OUT/name)
        rows=read(ROOT/'results/ticket_comparison.json')
        inputs=[{'id':r['id'],'query':r['query'],'prediction':r['v3_prediction']} for r in rows]
        assert len(inputs)==100 and len({r['id'] for r in inputs})==100
        save(OUT/'inputs.json',inputs)
        save(freeze,{'created_utc':utc(),'protocol':'Same exact original judge rubric, schema, pinned model and settings; reference labels and version names excluded from requests.',
          'rubric_sha256':sha(OUT/'rubric.txt'),'original_rubric_sha256':sha(OLD/'rubric.txt'),
          'sha256':{n:sha(OUT/n) for n in ['rubric.txt','schema.json','config.json','inputs.json']},
          'historical_judgment_sha256':{p.name:sha(p) for p in (OLD/'judgments').glob('*.json')},
          'v3_prediction_sha256':{p.name:sha(p) for p in (ROOT/'runs').glob('*.json')}})
    for name,h in read(freeze)['sha256'].items():assert sha(OUT/name)==h,name
    return read(OUT/'inputs.json')
def request_for(row):
    c=read(OUT/'config.json')
    return {'model':c['model'],'reasoning_effort':c['reasoning_effort'],'max_completion_tokens':c['max_completion_tokens'],'store':False,
      'messages':[{'role':'system','content':(OUT/'rubric.txt').read_text(encoding='utf-8')},{'role':'user','content':json.dumps({'query':row['query'],'predicted_category':row['prediction']},ensure_ascii=False)}],
      'response_format':{'type':'json_schema','json_schema':{'name':'routing_assessment','strict':True,'schema':read(OUT/'schema.json')}}}
def assess(row):
    path=OUT/'judgments'/f"{row['id']}.json";payload=request_for(row)
    if path.exists():
        x=read(path);assert x['request']==payload;legacy.validate(x['judgment'],row);return x
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    previous=list((OUT/'attempts').glob(row['id']+'_*.json'));offset=max([int(p.stem.rsplit('_',1)[1]) for p in previous],default=0)
    for k in range(1,4):
        attempt=offset+k;rec={'id':row['id'],'version':'v3','attempt':attempt,'request':payload,'started_utc':utc()}
        try:
            req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY'],'Content-Type':'application/json'})
            with opener.open(req,timeout=45) as response:answer=json.load(response)
            rec['response']=answer;choice=answer['choices'][0]
            if choice['finish_reason']!='stop' or choice['message'].get('refusal'):raise ValueError('Incomplete or refused judgment')
            judgment=legacy.validate(json.loads(choice['message']['content']),row)
            rec.update(status='OK',judgment=judgment,ended_utc=utc());save(OUT/'attempts'/f"{row['id']}_{attempt}.json",rec);save(path,rec);return rec
        except Exception as e:
            rec.update(status='ERROR',error_type=type(e).__name__,http_status=getattr(e,'code',None),ended_utc=utc());save(OUT/'attempts'/f"{row['id']}_{attempt}.json",rec)
            if getattr(e,'code',None) in [400,401,403,404]:break
            if k<3:time.sleep(k*2)
    raise RuntimeError('No valid judge response for '+row['id'])
def run():
    rows=prepare();(OUT/'attempts').mkdir(exist_ok=True);(OUT/'judgments').mkdir(exist_ok=True)
    # Protocol is frozen from the prior16-assessment pilot; no tuning against v3 scores.
    first=next(r for r in rows if r['id']=='t033')
    probe=assess(first);print('Initial saved v3 judge assessment validated: '+json.dumps(probe['judgment']),flush=True)
    random.Random(read(OUT/'config.json')['shuffle_seed']).shuffle(rows)
    failed=[];done=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        work={pool.submit(assess,r):r['id'] for r in rows}
        for f in concurrent.futures.as_completed(work):
            try:f.result()
            except Exception:failed.append(work[f])
            done+=1
            if done%10==0:print(f'V3 judge: {done}/100 processed; {len(failed)} unresolved',flush=True)
    save(OUT/'execution.json',{'processed':100,'valid':100-len(failed),'unresolved':failed,'completed_utc':utc()})
    if failed:raise RuntimeError('Judge assessments unresolved; resume without replacing accepted outputs.')
    analyze()
def analyze():
    inputs=prepare();refs={r['id']:r for r in read(ROOT/'results/ticket_comparison.json')};records=[]
    for r in sorted(inputs,key=lambda x:x['id']):
        x=read(OUT/'judgments'/f"{r['id']}.json");assert x['request']==request_for(r)
        j=legacy.validate(x['judgment'],r)
        ref=refs[r['id']]['v3_policy_intent']
        records.append({**r,**j,'alternative_intents':';'.join(j['alternative_intents']),'approved_policy_reference':ref,'exact_match':int(r['prediction']==ref),'judge_agrees_with_exact_match':j['score']==int(r['prediction']==ref),'judge_agrees_with_reference':j['proposed_intent']==ref,'needs_review':j['ambiguity'] or not j['score'] or j['proposed_intent']!=ref})
    old=read(OLD/'results/summary.json');frozen=read(OUT/'freeze.json')
    assert all(sha(OLD/'judgments'/n)==h for n,h in frozen['historical_judgment_sha256'].items())
    assert all(sha(ROOT/'runs'/n)==h for n,h in frozen['v3_prediction_sha256'].items())
    attempts=[read(p) for p in (OUT/'attempts').glob('*.json')]
    summary={'completed_utc':utc(),'model':read(OUT/'config.json')['model'],'valid_assessments':100,'judge_pass':sum(r['score'] for r in records),'judge_fail':sum(1-r['score'] for r in records),'exact_match_correct':100,
       'ambiguity_flags':sum(r['ambiguity'] for r in records),'review_ticket_ids':[r['id'] for r in records if r['needs_review']],
       'score_disagreement_ids':[r['id'] for r in records if not r['judge_agrees_with_exact_match']],
       'historical_judge_pass':{'baseline':old['baseline']['judge_pass'],'focused':old['focused']['judge_pass']},
       'prior_judgments_and_v3_predictions_unchanged':True,'rubric_identical_to_original':frozen['rubric_sha256']==frozen['original_rubric_sha256'],
       'recorded_api_attempts':len(attempts),'failed_attempts':sum(x['status']!='OK' for x in attempts),
       'usage':{'prompt_tokens':sum(x.get('response',{}).get('usage',{}).get('prompt_tokens',0) for x in attempts),'completion_tokens_including_reasoning':sum(x.get('response',{}).get('usage',{}).get('completion_tokens',0) for x in attempts)},
       'limitations':'Single new judge assessment per v3 output using prior frozen protocol; same100 known synthetic tickets, no new independent human calibration or held-out test. Prior t033 judge inconsistency remains historical evidence. Ambiguity flags are not auto-approvals.'}
    save(OUT/'summary.json',summary);save(OUT/'assessments.json',records)
    for name,items in [('assessments.csv',records),('review_needed.csv',[r for r in records if r['needs_review']])]:
        if items:
            with (OUT/name).open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':
    import sys
    try:(analyze if len(sys.argv)>1 and sys.argv[1]=='analyze' else run)()
    except Exception as e:print(json.dumps({'status':'ERROR','error_type':type(e).__name__,'message':str(e) if isinstance(e,RuntimeError) else 'Inspect saved local judge attempts.'}),flush=True);raise SystemExit(1)
