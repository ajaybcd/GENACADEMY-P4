"""Record the actual v3 responses as a new experiment; never alter prior runs."""
import concurrent.futures, json, logging, threading, uuid, os, ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote
import requests
from langsmith import Client
from experiment import ROOT, read, save, sha

def publish_judge(client,state,path):
    judged=read(ROOT/'llm_judge/summary.json')
    assert judged['valid_assessments']==100
    key='week4_p4_v3_llm_judge'
    state.setdefault('judge_feedback_records',{})
    lock=threading.Lock()
    def upload(ticket_id):
        if state['judge_feedback_records'].get(ticket_id):return
        raw=read(ROOT/'llm_judge/judgments'/f'{ticket_id}.json');j=raw['judgment'];run_id=state['records'][ticket_id]['run_id']
        client.create_feedback(run_id=run_id,session_id=state['project_id'],key=key,score=j['score'],
            feedback_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+'/'+key)),feedback_source_type='api',
            comment=j['rationale']+'\nProposed intent: '+j['proposed_intent']+'; ambiguity: '+str(j['ambiguity'])+'; alternatives: '+', '.join(j['alternative_intents']),
            source_info={'judge_model':judged['model'],'rubric_sha256':read(ROOT/'llm_judge/freeze.json')['rubric_sha256'],'provenance':'Actual saved v3 LLM-judge response imported separately from Exact Match; not human approval.','raw_judgment_sha256':sha(ROOT/'llm_judge/judgments'/f'{ticket_id}.json')})
        with lock:
            state['judge_feedback_records'][ticket_id]=True;save(path,state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for n,_ in enumerate(pool.map(upload,state['records']),1):
            if n%25==0:print(f'LangSmith judge feedback: {n}/100 recorded',flush=True)
    feedback=list(client.list_feedback(run_ids=[r['run_id'] for r in state['records'].values()],feedback_key=[key]))
    assert len(feedback)==100 and sum(f.score for f in feedback)==judged['judge_pass'],'Judge feedback readback differs'
    state['judge']={'feedback_key':key,'verified_records':100,'correct':judged['judge_pass'],'ambiguity_flags':judged['ambiguity_flags'],'disagreement_ids':judged['score_disagreement_ids'],'verified':True}
    save(path,state)

def publish_calibrated_judge(client,state,path):
    folder=ROOT/'llm_judge_v2'
    judged=read(folder/'summary.json');comparison=read(folder/'before_after.json')
    assert judged['valid_assessments']==100
    key='week4_p4_v3_llm_judge_v2'
    state.setdefault('judge_v2_feedback_records',{})
    lock=threading.Lock()
    old_key='week4_p4_v3_llm_judge';t033=state['records']['t033']['run_id']
    old=list(client.list_feedback(run_ids=[t033],feedback_key=[old_key]))
    assert len(old)==1 and old[0].score==0,'Original t033 judge score must remain0'
    def upload(ticket_id):
        if state['judge_v2_feedback_records'].get(ticket_id):return
        raw=read(folder/'judgments'/f'{ticket_id}.json');j=raw['judgment'];run_id=state['records'][ticket_id]['run_id']
        client.create_feedback(run_id=run_id,session_id=state['project_id'],key=key,score=j['score'],
          feedback_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+'/'+key)),feedback_source_type='api',
          comment=j['rationale']+'\nRubric v2; proposed intent: '+j['proposed_intent']+'; ambiguity: '+str(j['ambiguity']),
          source_info={'judge_model':judged['model'],'judge_rubric_version':'v2','rubric_sha256':read(folder/'freeze.json')['rubric_sha256'],
            'raw_judgment_sha256':sha(folder/'judgments'/f'{ticket_id}.json'),
            'provenance':'Actual new100-assessment rerun with the general billing/refund clarification authorized by the user. Prior rubric-v1 scores retained. Not an independent held-out evaluation.'})
        with lock:
            state['judge_v2_feedback_records'][ticket_id]=True;save(path,state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for n,_ in enumerate(pool.map(upload,state['records']),1):
            if n%25==0:print(f'LangSmith calibrated judge: {n}/100 recorded',flush=True)
    feedback=list(client.list_feedback(run_ids=[r['run_id'] for r in state['records'].values()],feedback_key=[key]))
    assert len(feedback)==100 and sum(f.score for f in feedback)==judged['judge_pass'],'New judge feedback readback differs'
    review=read(ROOT/'human_reviews/t033.json');human_key='week4_p4_v3_human_adjudicated_score'
    if not state.get('t033_human_review',{}).get('recorded'):
        client.create_feedback(run_id=t033,session_id=state['project_id'],key=human_key,score=review['human_adjudicated_score'],
          feedback_id=str(uuid.uuid5(uuid.NAMESPACE_URL,t033+'/'+human_key)),feedback_source_type='api',comment=review['note'],
          source_info={'approved_intent':review['approved_intent'],'reviewer':'User, explicit instruction in conversation','provenance':'API import of separately saved user adjudication; original automated score not edited.','human_review_sha256':sha(ROOT/'human_reviews/t033.json')})
    human=list(client.list_feedback(run_ids=[t033],feedback_key=[human_key]));prior=list(client.list_feedback(run_ids=[t033],feedback_key=[old_key]))
    assert len(human)==1 and human[0].score==1 and len(prior)==1 and prior[0].score==0
    state['t033_human_review']={'recorded':True,'verified':True,'feedback_key':human_key,'approved_intent':'refund_request','score':1,'old_judge_score_preserved':0}
    state['judge_v2']={'feedback_key':key,'verified':True,'verified_records':100,'correct':judged['judge_pass'],'ambiguity_flags':judged['ambiguity_flags'],
      'disagreement_ids':judged['score_disagreement_ids'],'before_judge_correct':comparison['before_judge_pass'],'delta_percentage_points':comparison['delta_percentage_points']}
    save(path,state)

def main():
    logging.disable(logging.CRITICAL)
    summary=read(ROOT/'results/comparison.json');assert summary['completed']==100 and summary['errors']==0
    # Requests' bundled CA list misses this machine's issuer. Use the existing
    # Windows trusted roots, with certificate verification still required.
    ca_path=ROOT/'inputs/windows_trusted_ca_bundle.pem'
    ca_path.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in ssl.create_default_context().get_ca_certs(binary_form=True)),encoding='ascii')
    session=requests.Session();session.trust_env=False;session.verify=str(ca_path)
    client=Client(session=session,auto_batch_tracing=False,timeout_ms=30000)
    original=read(ROOT.parent/'customer-support/live_runs/langsmith_evidence.json')
    dataset=client.read_dataset(dataset_id=original['dataset_id'])
    examples=list(client.list_examples(dataset_id=dataset.id))
    indexed={x.metadata.get('id'):x for x in examples}
    tickets=read(ROOT/'inputs/tickets.json');assert len(indexed)==100
    for r in tickets:
        ex=indexed[r['id']]
        assert ex.inputs=={'query':r['query']} and ex.outputs=={'intent':r['v3_policy_intent']},'Existing dataset differs from approved v3 policy'
    path=ROOT/'results/langsmith_v3_evidence.json'
    if path.exists():state=read(path)
    else:
        name='week4-p4-v3-refund-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        project=client.create_project(name,reference_dataset_id=dataset.id,
            description='Actual new v3 gpt-4o-mini responses imported with original request timestamps. Clarified refund-payment and cancellation routing; user approved product_issue for damaged goods. Original runs and labels untouched.',
            metadata={'prompt_version':'v3','model':'gpt-4o-mini','temperature':0,'prompt_sha256':read(ROOT/'inputs/freeze.json')['v3_prompt_sha256'],'provenance':'Actual model calls executed by p4/v3/experiment.py; original responses saved locally before recording traces. No classifier calls made during import.'})
        state={'dataset_id':str(dataset.id),'dataset_name':dataset.name,'project_id':str(project.id),'experiment_name':name,'records':{},'verified':False,
          'dataset_labels_verified_against_v3_policy':100,'original_dataset_modified':False,'original_runs_modified':False}
        save(path,state)
    lock=threading.Lock()
    def record(r):
        if state['records'].get(r['id'],{}).get('done'):return
        raw=read(ROOT/'runs'/f"{r['id']}.json");run_id=str(uuid.uuid5(uuid.NAMESPACE_URL,state['experiment_name']+'/'+r['id']))
        client.create_run(name='customer-support-v3',run_type='llm',inputs={'query':r['query']},outputs={'intent':raw['prediction']},
            project_name=state['experiment_name'],id=run_id,
            start_time=datetime.fromisoformat(raw['started_utc']),end_time=datetime.fromisoformat(raw['ended_utc']),
            reference_example_id=indexed[r['id']].id,
            extra={'metadata':{'id':r['id'],'prompt_version':'v3','model_requested':'gpt-4o-mini','model_returned':raw['response']['model'],'temperature':0,'prompt_sha256':read(ROOT/'inputs/freeze.json')['v3_prompt_sha256'],'openai_response_id':raw['response']['id'],'raw_response_sha256':sha(ROOT/'runs'/f"{r['id']}.json"),'provenance':'Actual saved OpenAI response; recorded after execution without regeneration.'}},tags=['week4-p4','v3','refund-rules'])
        client.create_feedback(run_id=run_id,session_id=state['project_id'],key='intent_exact_match',score=int(raw['prediction']==r['v3_policy_intent']),
            feedback_id=str(uuid.uuid5(uuid.NAMESPACE_URL,run_id+'/intent_exact_match')),feedback_source_type='api',
            comment='Exact Match against unchanged original dataset labels, verified equal to the user-approved v3 policy labels.')
        with lock:
            state['records'][r['id']]={'run_id':run_id,'prediction':raw['prediction'],'done':True};save(path,state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for n,_ in enumerate(pool.map(record,tickets),1):
            if n%20==0:print(f'LangSmith v3: {n}/100 recorded',flush=True)
    runs=list(client.list_runs(project_name=state['experiment_name'],run_type='llm'))
    remote={str(x.id):x for x in runs}
    diagnostic={'list_run_count':len(remote),'expected_run_count':100,'expected_project_id':state['project_id']}
    if len(remote)!=100:
        def primary(rec):return client.read_run(rec['run_id'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            primary_runs=list(pool.map(primary,state['records'].values()))
        diagnostic['primary_run_count']=len(primary_runs)
        diagnostic['primary_project_ids']=sorted({str(x.session_id) for x in primary_runs})
        remote={str(x.id):x for x in primary_runs}
    save(ROOT/'results/langsmith_readback_diagnostic.json',diagnostic)
    assert len(remote)==100,'Expected 100 recorded runs; found '+str(len(remote))
    for r in tickets:
        x=remote[state['records'][r['id']]['run_id']]
        assert x.inputs=={'query':r['query']} and x.outputs=={'intent':state['records'][r['id']]['prediction']} and not x.error,'Readback differs for '+r['id']
        assert str(x.session_id)==state['project_id'],'Run project differs for '+r['id']
    feedback=list(client.list_feedback(run_ids=list(remote),feedback_key=['intent_exact_match']))
    diagnostic['feedback_count']=len(feedback);diagnostic['feedback_score_sum']=sum(f.score or 0 for f in feedback)
    save(ROOT/'results/langsmith_readback_diagnostic.json',diagnostic)
    assert len(feedback)==100 and sum(f.score for f in feedback)==100,'Feedback readback: '+str(diagnostic)
    state.update(verified=True,verified_runs=100,verified_feedback=100,correct=100,
        comparison_url='https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/datasets/'+str(dataset.id)+'/compare?selectedSessions='+state['project_id'],
        completed_utc=datetime.now(timezone.utc).isoformat())
    save(path,state)
    if (ROOT/'llm_judge/summary.json').exists():publish_judge(client,state,path)
    if (ROOT/'llm_judge_v2/before_after.json').exists():publish_calibrated_judge(client,state,path)
    old_ids=parse_qs(urlsplit(original['comparison_url']).query)['selectedSessions'][0]
    state['all_versions_comparison_url']=state['comparison_url'].split('?')[0]+'?selectedSessions='+quote(old_ids+','+state['project_id'])
    save(path,state)
    print(json.dumps({k:v for k,v in state.items() if k not in ['records','judge_feedback_records','judge_v2_feedback_records']},indent=2),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        detail=str(e)
        for key in ['OPENAI_API_KEY','LANGSMITH_API_KEY']:
            if os.environ.get(key):detail=detail.replace(os.environ[key],'[REDACTED]')
        result={'status':'ERROR','error_type':type(e).__name__,'detail':detail[:2200]}
        save(ROOT/'results/langsmith_connection_error.json',result)
        print(json.dumps(result),flush=True);raise SystemExit(1)
