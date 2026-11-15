"""Isolated saved-prediction judge. No classifier calls or LangSmith mutations."""
import argparse, csv, hashlib, json, os, random, time, urllib.request, urllib.error, shutil, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'customer-support'
INTENTS = ['order_status','refund_request','product_issue','account_help','other']
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def csvwrite(path, rows):
    if not rows: return
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def api(endpoint, payload=None):
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key: raise RuntimeError('Saved OpenAI credential missing')
    req=urllib.request.Request('https://api.openai.com/v1/'+endpoint,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)
    except urllib.error.HTTPError as e: raise RuntimeError('OpenAI HTTP '+str(e.code)) from None
    except (urllib.error.URLError,TimeoutError): raise RuntimeError('OpenAI transport failure') from None
def probe():
    ids=sorted(m['id'] for m in api('models')['data'] if m['id'].startswith(('gpt-5','gpt-4.1','gpt-6')))
    save(ROOT/'evidence/model_availability.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'models':ids})
    print(json.dumps(ids))

SCHEMA={'type':'object','properties':{
    'score':{'type':'integer','enum':[0,1]},
    'correctness':{'type':'string','enum':['correct','incorrect']},
    'rationale':{'type':'string'},'ambiguity':{'type':'boolean'},
    'proposed_intent':{'type':'string','enum':INTENTS},
    'alternative_intents':{'type':'array','items':{'type':'string','enum':INTENTS}}},
    'required':['score','correctness','rationale','ambiguity','proposed_intent','alternative_intents'],'additionalProperties':False}

def source_hashes():
    hashes={}
    for folder,dirs,files in os.walk(SOURCE):
        dirs[:]=[d for d in dirs if d not in {'.venv','node_modules','__pycache__','.git'} and not d.startswith('tmp')]
        for name in files:
            if name.startswith(('.credentials','.env')) or name.endswith('.pyc'): continue
            p=Path(folder)/name
            hashes[p.relative_to(SOURCE).as_posix()]=sha(p)
    return hashes

def prepare():
    if (ROOT/'evidence/freeze.json').exists(): raise ValueError('Already prepared; frozen inputs cannot be replaced')
    inputs=ROOT/'inputs'; inputs.mkdir(exist_ok=True)
    for origin,name in [('live_runs/week4-p4-baseline-22024e81.csv','baseline.csv'),('live_runs/week4-p4-focused-7c8ba9cb.csv','focused.csv'),('outputs/final_review_snapshot.json','final_review_snapshot.json'),('outputs/langsmith_annotation_sync/sync_evidence.json','sync_evidence.json'),('outputs/fresh_failure_notes_before_categories.csv','policy_notes.csv')]:
        shutil.copyfile(SOURCE/origin,inputs/name)
    handout=SOURCE.parent.parent/'Evaluations Using LangSmith.docx'
    with zipfile.ZipFile(handout) as z:
        doc=ET.fromstring(z.read('word/document.xml'))
        text='\n'.join(t.text or '' for t in doc.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
    (inputs/'handout_extracted.txt').write_text(text,encoding='utf-8')
    bas=csvread(inputs/'baseline.csv'); foc=csvread(inputs/'focused.csv')
    assert len(bas)==len(foc)==100
    assert len({r['id'] for r in bas})==len({r['id'] for r in foc})==100
    assert {r['id'] for r in bas}=={r['id'] for r in foc}
    fi={r['id']:r for r in foc}; rows=[]
    for r in sorted(bas,key=lambda r:r['id']):
        s=fi[r['id']]
        assert r['query']==s['query'] and r['reference_intent']==s['reference_intent']
        for version,item in [('baseline',r),('focused',s)]:
            assert not item['error'] and item['prediction'] in INTENTS
            rows.append({'id':r['id'],'version':version,'query':r['query'],'prediction':item['prediction'],'run_id':item['run_id']})
    random.Random(read(ROOT/'config.json')['shuffle_seed']).shuffle(rows)
    save(inputs/'assessment_index.json',rows)
    save(ROOT/'schema.json',SCHEMA)
    paths=[ROOT/'config.json',ROOT/'rubric.txt',ROOT/'schema.json',*inputs.iterdir()]
    save(ROOT/'evidence/freeze.json',{'created_at':datetime.now(timezone.utc).isoformat(),'sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},'original_project_sha256':source_hashes(),'handout_sha256':sha(handout),'pilot_gate':'Validate complete structured outputs and manually inspect boundary cases for rule adherence; disagreement with labels does not fail the pilot. No rubric changes based on aggregate improvement.'})
    print('Prepared 200 assessments; inputs, rubric, settings and original project frozen.')

def check_freeze():
    frozen=read(ROOT/'evidence/freeze.json')
    for p,h in frozen['sha256'].items():
        if sha(ROOT/p)!=h: raise ValueError('Frozen file changed: '+p)
    return frozen

def request_for(row):
    c=read(ROOT/'config.json')
    return {'model':c['model'],'reasoning_effort':c['reasoning_effort'],'max_completion_tokens':c['max_completion_tokens'],'store':False,
        'messages':[{'role':'system','content':(ROOT/'rubric.txt').read_text(encoding='utf-8')},
        {'role':'user','content':json.dumps({'query':row['query'],'predicted_category':row['prediction']},ensure_ascii=False)}],
        'response_format':{'type':'json_schema','json_schema':{'name':'routing_assessment','strict':True,'schema':SCHEMA}}}

def validate(j,row):
    if not isinstance(j,dict) or set(j)!=set(SCHEMA['required']): raise ValueError('Unexpected judgment fields')
    if type(j['score']) is not int or j['score'] not in (0,1): raise ValueError('Invalid score')
    if type(j['ambiguity']) is not bool: raise ValueError('Invalid ambiguity')
    if j['proposed_intent'] not in INTENTS: raise ValueError('Invalid intent')
    if not isinstance(j['rationale'],str) or not 12<=len(j['rationale'])<=1800: raise ValueError('Invalid rationale')
    alternatives=j['alternative_intents']
    if not isinstance(alternatives,list) or any(x not in INTENTS or x==j['proposed_intent'] for x in alternatives) or len(set(alternatives))!=len(alternatives): raise ValueError('Invalid alternatives')
    if alternatives and not j['ambiguity']: raise ValueError('Alternatives require ambiguity')
    if j['correctness']!=('correct' if j['score'] else 'incorrect'): raise ValueError('Correctness-score conflict')
    if j['score']!=int(row['prediction']==j['proposed_intent']): raise ValueError('Score-intent conflict')
    return j

def assess(row,phase):
    key=row['id']+'_'+row['version']; dest=ROOT/'judgments'/f'{key}.json'
    if dest.exists():
        saved=read(dest); validate(saved['judgment'],row)
        assert saved['request']==request_for(row)
        return saved
    payload=request_for(row); config=read(ROOT/'config.json')
    previous=[int(p.stem.rsplit('_',1)[1]) for p in (ROOT/'attempts').glob(key+'_*.json')]
    offset=max(previous,default=0)
    for local_attempt in range(1,config['max_attempts']+1):
        attempt=offset+local_attempt
        record={'id':row['id'],'version':row['version'],'phase':phase,'attempt':attempt,'started_at':datetime.now(timezone.utc).isoformat(),'request':payload}
        record['status']='STARTED'
        save(ROOT/'attempts'/f'{key}_{attempt}.json',record)
        try:
            raw=api('chat/completions',payload)
            record['response']=raw
            choice=raw['choices'][0]
            if choice['finish_reason']!='stop' or choice['message'].get('refusal'): raise ValueError('Refused or incomplete response')
            j=validate(json.loads(choice['message']['content']),row)
            record.update(status='OK',judgment=j)
            save(ROOT/'attempts'/f'{key}_{attempt}.json',record)
            save(dest,record)
            return record
        except Exception as e:
            record.update(status='ERROR',error_type=type(e).__name__,error=str(e) if isinstance(e,(ValueError,RuntimeError)) else 'Malformed API response')
            save(ROOT/'attempts'/f'{key}_{attempt}.json',record)
            if isinstance(e,RuntimeError) and any(str(n) in str(e) for n in [400,401,403,404]): break
            if local_attempt<config['max_attempts']: time.sleep(2**local_attempt)
    raise RuntimeError('Assessment failed: '+key)

def run(phase):
    check_freeze(); c=read(ROOT/'config.json')
    prior=ROOT/'evidence'/f'{phase}_execution.json'
    if prior.exists():
        shutil.copyfile(prior,ROOT/'evidence'/f'{phase}_execution_prior_{sha(prior)[:12]}.json')
    if phase=='full':
        gate=read(ROOT/'evidence/pilot_review.json')
        assert gate['decision']=='PROCEED' and gate['rubric_sha256']==sha(ROOT/'rubric.txt')
    rows=read(ROOT/'inputs/assessment_index.json')
    if phase=='pilot': rows=[r for r in rows if r['id'] in c['pilot_ticket_ids']]
    failed=[]; completed=0
    with ThreadPoolExecutor(max_workers=c['concurrency']) as pool:
        work={pool.submit(assess,r,phase):r for r in rows}
        for future in as_completed(work):
            r=work[future]
            try: future.result(); completed+=1
            except Exception: failed.append(r['id']+'_'+r['version'])
            if (completed+len(failed))%10==0 or completed+len(failed)==len(rows):
                print(f'{phase}: {completed}/{len(rows)} completed, {len(failed)} failed',flush=True)
    save(ROOT/'evidence'/f'{phase}_execution.json',{'completed':completed,'expected':len(rows),'failed':failed,'completed_at':datetime.now(timezone.utc).isoformat()})
    if failed: raise RuntimeError('Incomplete evaluation; inspect attempts')

if __name__=='__main__':
    command=argparse.ArgumentParser(); command.add_argument('action'); args=command.parse_args()
    if args.action=='probe': probe()
    elif args.action=='prepare': prepare()
    elif args.action in ('pilot','full'): run(args.action)
    elif args.action in ('analyze','verify'):
        from analysis import analyze, verify
        if args.action=='analyze': print(json.dumps(analyze(),indent=2))
        else: verify()
    else: raise SystemExit('Unknown action')
