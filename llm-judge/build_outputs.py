"""Build report, execute analysis notebook, and package a credential-free add-on."""
import contextlib, io, json, sys, traceback, zipfile
from pathlib import Path
from analysis import analyze, verify
from judge import ROOT, read, save, sha, csvread

def notebook(summary):
    cells=[]
    def md(text): cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
    def code(text): cells.append({'cell_type':'code','metadata':{},'source':text.splitlines(True),'execution_count':None,'outputs':[]})
    md('# Customer support LLM judge add-on\n\nOffline analysis of 200 preserved predictions. Judge feedback remains separate from reference labels. Run all cells with Python 3.10+; no API calls or external packages. See METHOD.md for rubric choices and official documentation sources. The implementing AI inspected the pilot; independent participant adjudication remains open.')
    code("from pathlib import Path\nimport sys, json, csv\nROOT = Path.cwd()\nif not (ROOT / 'inputs').exists():\n    ROOT = ROOT / 'p4' / 'llm-judge'\nassert (ROOT / 'inputs').exists(), 'Run from llm-judge or the Week-4 workspace'\nsys.path.insert(0, str(ROOT.resolve()))\nfrom analysis import analyze\nsummary = analyze()\nprint('Completed assessments:', sum(summary[v]['assessments'] for v in ('baseline','focused')))\nprint('Model:', json.loads((ROOT/'config.json').read_text())['model'])")
    md('## Method\n\nEach request contains the same frozen system rubric and only query plus predicted_category. No version, ground truth, human approval, experiment name, existing score or note is sent. Structured feedback includes score, correctness, rationale, ambiguity, proposed intent and alternatives. Valid pilot assessments are counted once in the final 200. Refusals, truncation, invalid schema and inconsistent fields are failures requiring retry or explicit unresolved status.\n\nThe declared policy sends non-delivery refund requests to order_status and damaged-goods refund requests to product_issue. Missing refund money after returns and unwanted-order cancellations go to refund_request. This overlaps the focused prompt policy and does not independently validate the policy choice. Ambiguity can coexist with a definite rubric score.')
    code("print('Measure                         Baseline Focused')\nfor label,key in [('Original-label Exact Match','original_exact_match'),('Reviewed-label Exact Match','reviewed_exact_match'),('LLM rubric passes','judge_pass'),('Ambiguity flags','ambiguity_flags'),('Proposed intent vs original','judge_vs_original_label'),('Proposed intent vs reviewed','judge_vs_reviewed_label'),('Score agrees with original EM','score_vs_original_em'),('Score agrees with reviewed EM','score_vs_reviewed_em')]:\n    print(f'{label:32} {summary[\"baseline\"][key]:3}/100 {summary[\"focused\"][key]:3}/100')")
    md('## Paired changes and consistency\n\nDifferences use preserved predictions for the same tickets. The 86 unchanged predictions produce identical judge requests twice; t033 receives conflicting scores on these identical inputs. This is evidence of judge instability, with only two calls per input. The 14 changed predictions contribute +2 passes, while the t033 inconsistency contributes -1, producing the observed +1 total. No judgment is replaced to force agreement. Paraphrases share 25 seed families, so 100 tickets do not constitute 100 independent held-out trials.')
    code("print(json.dumps(summary['paired'], indent=2))\nprint('Per original reference category:')\nprint(json.dumps(summary['by_reference_intent'], indent=2))\nprint('Per participant failure category, joined only after judging:')\nprint(json.dumps(summary['by_review_failure_category'], indent=2))\nprint('Passes per family, four paraphrases each:')\nprint(json.dumps(summary['by_seed_family'], indent=2))")
    md('## Disagreements and human review\n\nJudge disagreement is a review request, not permission to change a label. Participant approval means reviewed, not correct. t046 was changed by the participant from product_issue to refund_request; both Exact Match comparisons preserve that fact. The judge uses the explicit damaged-product rule, which may disagree with that human policy preference.')
    code("def load_csv(name):\n    with (ROOT/'results'/name).open(encoding='utf-8',newline='') as stream:\n        return list(csv.DictReader(stream))\ndisagreements = load_csv('disagreements.csv') if (ROOT/'results/disagreements.csv').exists() else []\nprint('Disagreement assessments:', len(disagreements))\nfor r in disagreements:\n    print(r['id'], r['version'], 'prediction='+r['prediction'], 'judge='+r['proposed_intent'], 'original='+r['original_label'], 'reviewed='+r['reviewed_label'], 'score='+r['score'])\nprint('Tickets needing review:', ', '.join(summary['review_ticket_ids']))")
    md('## Meaningful examples\n\nExamples cover policy wins, regressions, a reviewed-label disagreement and a routine pass. These were selected for routing mechanisms, not to establish model superiority.')
    code("rows=load_csv('assessments.csv')\nfor ticket in ['t004','t024','t028','t033','t046','t094']:\n    for r in rows:\n        if r['id']==ticket:\n            print(f\"{ticket} {r['version']}: prediction={r['prediction']}; score={r['score']}; proposed={r['proposed_intent']}; ambiguity={r['ambiguity']}\")\n            print(' Query:', r['query'])\n            print(' Rationale:', r['rationale'])")
    md('## Cost, failures and limits\n\nCost is estimated from returned token usage, including rejected responses with usage. Transport failures without usage have unknown billing. The judge can share model-family biases with the classifier, infer the wrong intent, anchor on predictions or inconsistently flag ambiguity. The pilot is not an independently human-labelled calibration set. No significance or real-world improvement claim follows from this reused synthetic sample. Neither the labels nor the original 93/100 versus 93/100 reviewed result is changed.')
    code("print(json.dumps(summary['usage'], indent=2))\nprint('Recorded failure types:', summary['failure_types'])\nprint('Rejected-response score changes:', summary['retry_sensitivity']['score_changes'])\nprint('Rejected-response proposed-intent changes:', summary['retry_sensitivity']['proposed_intent_changes'])\nprint('Pilot review:')\nprint((ROOT/'evidence/pilot_review.json').read_text())\nprint('Frozen input hashes verified by analyze().')")
    scope={'__name__':'__notebook__'}; old=Path.cwd()
    import os
    os.chdir(ROOT)
    try:
        execution=0
        for i,c in enumerate(cells):
            c['id']=f'judge-cell-{i:02d}'
            if c['cell_type']!='code': continue
            execution+=1; c['execution_count']=execution; out=io.StringIO()
            with contextlib.redirect_stdout(out): exec(compile(''.join(c['source']),f'notebook-cell-{i}','exec'),scope)
            c['outputs']=[{'output_type':'stream','name':'stdout','text':out.getvalue().splitlines(True)}]
    finally: os.chdir(old)
    nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':sys.version.split()[0]}},'nbformat':4,'nbformat_minor':5}
    save(ROOT/'judge_analysis.ipynb',nb)
    save(ROOT/'evidence/notebook_execution.json',{'status':'PASS','code_cells_executed':execution,'execution_method':'Sequential execution of the exact notebook Python sources in a shared namespace; no IPython-only features or API calls','python':sys.version.split()[0]})

def report(s):
    b=s['baseline']; f=s['focused']; usage=s['usage']; pair=s['paired']
    table='\n'.join(f'| {title} | {b[k]}/100 | {f[k]}/100 |' for title,k in [('Original-label Exact Match','original_exact_match'),('Reviewed-label Exact Match','reviewed_exact_match'),('LLM rubric passes','judge_pass'),('Ambiguity flags','ambiguity_flags'),('Score agrees with original-label EM','score_vs_original_em'),('Score agrees with reviewed-label EM','score_vs_reviewed_em')])
    examples=csvread(ROOT/'results/assessments.csv')
    example_text='\n\n'.join(f"**{r['id']} {r['version']}** — prediction `{r['prediction']}`, judge {r['score']}, proposed `{r['proposed_intent']}`, ambiguity {r['ambiguity']}. {r['rationale']}" for r in examples if (r['id'],r['version']) in [('t004','baseline'),('t004','focused'),('t024','focused'),('t028','focused'),('t046','baseline'),('t046','focused')])
    text=f'''# LLM judge add-on report

All 200 saved predictions received validated judge assessments under one frozen routing rubric. The judge passed {b['judge_pass']}/100 baseline and {f['judge_pass']}/100 focused predictions, an observed difference of {pair['judge_delta_percentage_points']:+d} percentage point **under that rubric**. An identical-input inconsistency on t033 makes this difference unreliable as evidence of classifier improvement. The authoritative reviewed-label Exact Match result remains 93/100 versus 93/100. Judge feedback does not replace it or establish that the reviewed labels are wrong.

| Measure | Baseline | Focused |
|---|---:|---:|
{table}

## What was evaluated

The inputs are the fresh saved baseline and focused LangSmith prediction exports, each covering the same 100 synthetic tickets from 25 seed families with paraphrases. No classifier was rerun. The original labels yield 92/100 versus 94/100. Applying the participant's t046 correction equally to both predictions yields 93/100 versus 93/100, seven wins, seven regressions and 86 unchanged passes. The older Evaluation tab's 92% to 97% belongs to a separate broader repository revision. Prior approved failure cases remain 11/11 older and 14/14 fresh; approval records review completion, not objective correctness.

## Method and pilot

Judge model: `{read(ROOT/'config.json')['model']}`; low reasoning, maximum 2048 completion tokens, provider-default temperature, no tools, store false. The snapshot was confirmed available through authenticated model listing. It was chosen for structured task fit and modest cost, not demonstrated superiority. Settings, exact rubric and schema are saved separately. [Official model guidance and rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) informed the implementation.

Requests contain only the frozen rubric and ticket query plus prediction, without labels, approvals, version names, existing scores, experiment names or notes. Baseline and focused use identical criteria and a fixed shuffled order. The 16-assessment pilot spans eight tickets and all five categories. The implementing AI inspected the accepted rationales before the full run; this is not independent human calibration. Pilot judgments are included once in the 200. No model or rubric changes were made after the pilot. Invalid/inconsistent output is rejected, retained and retried using identical inputs.

The policy prioritizes non-delivery over a refund remedy (order_status), delivered-product defects over a refund remedy (product_issue), and routes missing refund payments after returns and unwanted-order cancellation with refund to refund_request. Account problems must be actual access, detail-change or checkout failures; general discounts/sales are other. Ambiguity flags surface credible alternate routing choices without automatically awarding a pass. The precedence policy is an explicit choice informed by existing notes; it overlaps the focused classifier prompt and is not an independent validation of that policy. Full details are in [METHOD.md](METHOD.md) and [rubric.txt](rubric.txt).

## Paired findings and review

Judge paired changes: {json.dumps(pair['changes'])}. Proposed-intent inconsistencies across versions: {pair['proposed_intent_inconsistency_ids'] or 'none'}. Ambiguity-flag inconsistencies: {pair['ambiguity_inconsistency_ids'] or 'none'}. These limited checks do not establish repeatability or independence from the presented prediction. Among {s['retry_sensitivity']['parsed_rejected_responses']} parsed rejected responses, retrying changed {s['retry_sensitivity']['score_changes']} scores and {s['retry_sensitivity']['proposed_intent_changes']} proposed intents relative to accepted judgments; details remain in summary.json.

Tickets flagged for participant review: {', '.join(s['review_ticket_ids']) or 'none'}. [review_needed.csv](results/review_needed.csv) contains every flagged assessment, its rationale, alternatives and both labels. [disagreements.csv](results/disagreements.csv) separates disagreements with original and reviewed references. A flag is not an approval or automatic label change.

The t046 damaged-laptop refund case is the key policy disagreement: the participant selected refund_request, while the frozen underlying-problem rule proposes product_issue. Both positions remain visible. The judge evaluates a declared rule, so any resulting advantage for focused predictions is conditional on that rule, not evidence that the participant's policy preference is invalid.

The t033 overcharge case is a judge inconsistency: both classifiers predict refund_request and both judge requests are identical. One judge response accepts the refund routing; the other calls it account_help because it interprets the overcharge as a checkout failure. This is not a classifier regression. Across {pair['identical_input_pairs']} identical-input pairs, it is the only score disagreement. Changed predictions contribute {pair['changed_prediction_score_delta']:+d} judge passes; identical-input variation contributes {pair['identical_input_score_delta']:+d}. Preserve both judgments and ask the participant to adjudicate the boundary; do not rerun until the scores agree.

{example_text}

## Usage, preservation and limitations

There were {usage['api_attempts']} recorded API attempts, including {usage['failed_attempts']} rejected/failed attempts. Returned usage totals {usage['prompt_tokens']:,} prompt tokens ({usage['cached_prompt_tokens']:,} cached) and {usage['completion_tokens_including_reasoning']:,} completion tokens including reasoning. Estimated returned-usage cost is **${usage['estimated_cost_usd']:.4f}**, calculated from published rates rather than an invoice. Attempts without returned usage may have unknown billing. The initial run was interrupted to shorten stalled transport calls from 120 to 30 seconds; at most {usage['interrupted_unrecorded_requests_maximum']} additional in-flight requests lack usage records. This changed no rubric or model setting. Raw recorded attempts and failure types are retained; no unresolved final assessments remain when validation passes.

The source-project hash inventory confirms preservation of its existing artifacts. No LangSmith writes were performed: its 8/8 baseline and 7/7 focused completed queues, 15 run reviews for 14 tickets and 75 verified feedback records remain as before. No existing predictions, labels, Excel approvals, annotations, report or notebook were changed. Existing evaluation had no LLM judge; this folder is the separate add-on.

This is descriptive reuse of synthetic paraphrases, not independent held-out validation. A single judge can share model-family biases, anchor on candidate predictions, misinterpret policy or vary across calls; retries select internally valid output and do not guarantee semantic accuracy. Ambiguity estimates are advisory. Independent human adjudication of flagged cases and a future held-out family sample are needed before automated approval. No statistical significance, production benefit or unconditional improvement is claimed.

**Interpretation:** the judge adds a policy-specific view and exposes where the label correction and underlying-problem rubric differ. It does not change the original final conclusion of no net improvement under the participant-reviewed labels.
'''
    (ROOT/'REPORT.md').write_text(text,encoding='utf-8')

def package():
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in {'.venv','__pycache__','.git'} or x.startswith('tmp') for x in p.relative_to(ROOT).parts) and p.name not in {'llm-judge-addon.zip','artifact_manifest.json'}]
    assert not any(p.name.startswith(('.credentials','.env')) or p.suffix=='.pyc' for p in paths)
    for p in paths:
        text=p.read_text(encoding='utf-8')
        assert ('sk'+'-proj-') not in text and ('lsv2'+'_pt_') not in text, 'Credential-like content found'
    manifest={'sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)},'credentials_included':False,'temporary_environments_included':False,'publication':'Prepared locally only; no GitHub push or LangSmith mutation'}
    save(ROOT/'artifact_manifest.json',manifest)
    with zipfile.ZipFile(ROOT/'llm-judge-addon.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in paths+[ROOT/'artifact_manifest.json']: z.write(p,'llm-judge/'+p.relative_to(ROOT).as_posix())
    print('Packaged',len(paths)+1,'files; credentials and environments excluded.')

if __name__=='__main__':
    import sys
    s=analyze(); report(s); notebook(s); verify(); package()
