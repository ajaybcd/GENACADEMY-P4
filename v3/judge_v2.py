"""Calibrated judge rubric v2; keeps human review and all old scores separate."""
import copy, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
import judge_v3 as engine
from experiment import ROOT, read, save, sha

PREVIOUS=ROOT/'llm_judge'
OUT=ROOT/'llm_judge_v2'
engine.OUT=OUT

def utc():return datetime.now(timezone.utc).isoformat()
def prepare():
    OUT.mkdir(exist_ok=True)
    review_path=ROOT/'human_reviews/t033.json'
    original=read(PREVIOUS/'judgments/t033.json')
    review={'ticket_id':'t033','reviewer':'User, explicitly authorized in this conversation','recorded_utc':utc(),
      'approved_intent':'refund_request','human_adjudicated_score':1,
      'classifier_prediction':'refund_request','previous_judge_score':original['judgment']['score'],
      'previous_judge_proposed_intent':original['judgment']['proposed_intent'],
      'note':'Human review: refund_request is correct. The customer disputes an overcharge and requests reimbursement. Mentioning checkout does not establish a technical checkout failure. The v3 prediction is accepted.',
      'authorization':'User explicitly requested refund_request for t033, saving this review separately, clarifying the judge rubric, and rerunning all100.',
      'old_judgment_sha256':sha(PREVIOUS/'judgments/t033.json'),
      'separate_from_automated_judge':True,'reference_label_changed':False,'classifier_prediction_changed':False}
    if not review_path.exists():save(review_path,review)
    else:
        existing=read(review_path);assert existing['approved_intent']=='refund_request' and existing['human_adjudicated_score']==1
    freeze_path=OUT/'freeze.json'
    if not freeze_path.exists():
        for name in ['schema.json','config.json','inputs.json']:shutil.copyfile(PREVIOUS/name,OUT/name)
        old=(PREVIOUS/'rubric.txt').read_text(encoding='utf-8')
        old_refund='- refund_request: returns, money back, cancellation with refund when no delivery/product defect is stated, and missing/delayed refund payments after a return. Money not appearing on a card is refund status, not order delivery or account help.'
        new_refund=old_refund+' Overcharges, duplicate charges, incorrect charged amounts, and requests to refund a price difference also belong to refund_request. A disputed completed charge remains refund_request when the requested action is reimbursement, including when the message mentions checkout or a card.'
        old_account='- account_help: login/password/account access and changing account/address/payment details; actual account or checkout failures. Merely mentioning an order number, credit card, or checkout does not establish this category.'
        new_account='- account_help: login/password/account access and changing account/address/payment details; actual technical account or checkout failures, such as being unable to submit payment or complete checkout because of an error. A completed charge with a disputed amount is a monetary refund dispute, not by itself a technical checkout failure. Merely mentioning an order number, credit card, or checkout does not establish account_help.'
        assert old_refund in old and old_account in old
        rubric=old.replace('routing policy v1.','routing policy v2.').replace(old_refund,new_refund).replace(old_account,new_account)
        (OUT/'rubric.txt').write_text(rubric,encoding='utf-8')
        save(OUT/'rubric_change.json',{'version':'v2','change':'Clarify monetary reimbursement versus technical checkout failure for all tickets, based on user t033 adjudication. No ticket IDs, exact example wording, human scores, or reference labels enter the judge requests.','previous_rubric_sha256':sha(PREVIOUS/'rubric.txt'),'new_rubric_sha256':sha(OUT/'rubric.txt'),'model_or_settings_changed':False,'classifier_outputs_changed':False})
        save(freeze_path,{'created_utc':utc(),'judge_rubric_version':'v2','protocol':'Full100 saved v3 outputs rerun with the general overcharge/refund policy clarification. Same pinned model, schema and settings. Calibration uses a known disagreement; not independent validation.',
          'rubric_sha256':sha(OUT/'rubric.txt'),'original_rubric_sha256':sha(PREVIOUS/'rubric.txt'),
          'sha256':{n:sha(OUT/n) for n in ['rubric.txt','schema.json','config.json','inputs.json']},
          'historical_judgment_sha256':{p.name:sha(p) for p in (engine.OLD/'judgments').glob('*.json')},
          'previous_v3_judgment_sha256':{p.name:sha(p) for p in (PREVIOUS/'judgments').glob('*.json')},
          'v3_prediction_sha256':{p.name:sha(p) for p in (ROOT/'runs').glob('*.json')},
          'human_review_sha256':sha(review_path)})
    frozen=read(freeze_path)
    for n,h in frozen['sha256'].items():assert sha(OUT/n)==h,n
    for n,h in frozen['previous_v3_judgment_sha256'].items():assert sha(PREVIOUS/'judgments'/n)==h,n
    assert sha(review_path)==frozen['human_review_sha256']
    # Only the system rubric changes in each fresh judge request.
    for row in read(OUT/'inputs.json'):
        before=read(PREVIOUS/'judgments'/f"{row['id']}.json")['request']
        expected=copy.deepcopy(before);expected['messages'][0]['content']=(OUT/'rubric.txt').read_text(encoding='utf-8')
        assert engine.request_for(row)==expected,row['id']
    print('Prepared judge rubric v2; user t033 review saved separately; previous100 judgments preserved.',flush=True)

def analyze():
    summary=read(OUT/'summary.json');frozen=read(OUT/'freeze.json')
    summary['judge_rubric_version']='v2'
    summary['limitations']='Same pinned model, schema and settings, with a new user-authorized general overcharge/refund rubric clarification. Calibrated on known t033 disagreement and rerun on the same100 known synthetic tickets; not independent held-out validation. Human adjudication is separately saved; ambiguity flags are not automatic approvals.'
    save(OUT/'summary.json',summary)
    previous=read(PREVIOUS/'summary.json');old={r['id']:r for r in read(PREVIOUS/'assessments.json')}
    new={r['id']:r for r in read(OUT/'assessments.json')}
    assert len(old)==len(new)==100
    for n,h in frozen['previous_v3_judgment_sha256'].items():assert sha(PREVIOUS/'judgments'/n)==h,n
    for n,h in frozen['v3_prediction_sha256'].items():assert sha(ROOT/'runs'/n)==h,n
    changes=[]
    for tid in sorted(new):
        a,b=old[tid],new[tid]
        assert a['query']==b['query'] and a['prediction']==b['prediction'] and a['approved_policy_reference']==b['approved_policy_reference']
        changes.append({'id':tid,'before_score':a['score'],'after_score':b['score'],'before_proposed_intent':a['proposed_intent'],'after_proposed_intent':b['proposed_intent'],'before_ambiguity':a['ambiguity'],'after_ambiguity':b['ambiguity'],
          'change':'WIN' if b['score']>a['score'] else 'REGRESSION' if b['score']<a['score'] else 'UNCHANGED_PASS' if b['score'] else 'UNCHANGED_FAIL'})
    result={'completed_utc':utc(),'assessments':100,'before_rubric_version':'v1','after_rubric_version':'v2','before_judge_pass':previous['judge_pass'],'after_judge_pass':summary['judge_pass'],
      'delta_percentage_points':summary['judge_pass']-previous['judge_pass'],'classifier_exact_match_before':100,'classifier_exact_match_after':100,
      'paired_changes':{c:sum(r['change']==c for r in changes) for c in ['WIN','REGRESSION','UNCHANGED_PASS','UNCHANGED_FAIL']},
      'score_changed_ids':[r['id'] for r in changes if r['before_score']!=r['after_score']],
      'proposed_intent_changed_ids':[r['id'] for r in changes if r['before_proposed_intent']!=r['after_proposed_intent']],
      'new_score_disagreement_ids':summary['score_disagreement_ids'],'new_ambiguity_flags':summary['ambiguity_flags'],'new_review_ticket_ids':summary['review_ticket_ids'],
      't033':{'user_review_intent':'refund_request','human_score_separately_saved':1,'before_judge_score':old['t033']['score'],'after_judge_score':new['t033']['score'],'after_judge_proposed_intent':new['t033']['proposed_intent']},
      'previous_judgments_preserved':True,'classifier_predictions_preserved':True,'model_schema_settings_unchanged':True,'recorded_api_attempts':summary['recorded_api_attempts'],'failed_attempts':summary['failed_attempts'],
      'limitation':'Rubric was calibrated using known t033 disagreement and then rerun on the same100 known synthetic tickets. A single rerun, not independent held-out validation or a general reliability guarantee. Ambiguity flags are not automatic approvals.'}
    save(OUT/'before_after.json',result);save(OUT/'paired_changes.json',changes)
    print(json.dumps(result,indent=2),flush=True)
    return result

if __name__=='__main__':
    try:
        prepare()
        if len(sys.argv)>1 and sys.argv[1]=='prepare':pass
        else:
            if len(sys.argv)<2 or sys.argv[1]!='analyze':engine.run()
            analyze()
    except Exception as e:print(json.dumps({'status':'ERROR','error_type':type(e).__name__,'message':str(e) if isinstance(e,RuntimeError) else 'Inspect saved rubric-v2 attempts.'}),flush=True);raise SystemExit(1)
