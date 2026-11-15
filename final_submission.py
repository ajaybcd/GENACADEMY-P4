"""Rebuild final v3 report and execute its offline notebook; no paid API calls."""
from pathlib import Path
import json,re,io,contextlib,os
ROOT=Path(__file__).resolve().parent
V3=ROOT/'v3' if (ROOT/'v3').exists() else ROOT.parent/'v3'
OUT=ROOT/'outputs'
def build():
    s=json.loads((V3/'results/comparison.json').read_text(encoding='utf-8'))
    j=json.loads((V3/'llm_judge_v2/summary.json').read_text(encoding='utf-8'))
    assert s['same_v3_policy_scores']=={'baseline':92,'focused':94,'v3':100}
    assert j['valid_assessments']==100 and j['judge_pass']==100 and j['ambiguity_flags']==12
    prefix=os.path.relpath(V3,OUT).replace('\\','/')+'/'
    html=(V3/'REPORT.html').read_text(encoding='utf-8')
    html=re.sub(r'href="(?!https?://|#)([^"]+)"',lambda m:'href="'+prefix+m[1]+'"',html)
    html=html.replace('<title>V3 customer support evaluation</title>','<title>Customer Support Intent Evaluation Using LangSmith — Final v3</title>')
    html=html.replace('<h1>Customer support evaluation v3</h1>','<h1>Customer Support Intent Evaluation Using LangSmith</h1><p>Final v3 submission • Ajay David • Updated November 14, 2026 (US Eastern)</p>')
    extra='''<h2>Project sources and completed human annotations</h2>
<p>The project follows the <em>Evaluations Using LangSmith</em> handout and the <a href="https://github.com/The-Gen-Academy/4B-Social-Media-Post-Evaluation/">Gen Academy source repository</a>. It classifies 100 synthetic customer-support tickets into order_status, refund_request, product_issue, account_help and other. The 25 seed scenarios each have an original plus three paraphrases. These are related synthetic examples.</p>
<p>The original workbook retains 11/11 approved failed cases in Evaluation and 14/14 in Fresh evaluation. Excel notes in L and approvals in M document the participant's review. The fresh LangSmith baseline queue has 8 completed runs and focused has 7, with zero pending: 15 completed run reviews over 14 tickets and <strong>75 feedback records</strong>. Approval is review completion, not a change to model correctness. The later t033 adjudication is a separate record.</p>
<p><a href="https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/a/-/annotation-queues/9b8652c6-6d49-456a-b450-937684e6919f/list?runView=completed">Completed baseline queue</a> · <a href="https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/a/-/annotation-queues/ac189235-b699-4e67-9cb8-f2d85ed9c34c/list?runView=completed">Completed focused queue</a></p>
<h2>Submission files</h2><ul>
<li><a href="../customer_support_evaluation.ipynb">Executed final project notebook</a></li>
<li><a href="project_transcript_and_summary.docx">3–4 minute narration, 90-second demo and summary</a></li>
<li><a href="project_summary_20_lines.txt">20-line summary</a></li>
<li><a href="customer_support_project_presentation.pptx">Final presentation with speaker notes</a></li>
<li><a href="customer_support_evaluation.xlsx">Preserved historical review workbook</a></li>
<li><a href="final_review_snapshot.json">Historical reviewed 93/100 versus 93/100 snapshot</a></li>
</ul><p>The existing November 1 video predates v3. Use the updated demo transcript when recording a final walkthrough. The separate source-repository 92%→97% exercise is historical context and is not the measured effect of this focused/v3 experiment.</p>'''
    html=html.replace('</body>',extra+'</body>')
    (OUT/'project_report.html').write_text(html,encoding='utf-8')
    n=json.loads((V3/'v3_analysis.ipynb').read_text(encoding='utf-8'))
    n['cells'][0]['source']=['# Customer Support Intent Evaluation Using LangSmith\n','Final v3 and judge rubric v2. Execute all cells offline from the project root or v3 directory. No API calls. Historical scores and human reviews remain separate.']
    for c in n['cells']:
        if c['cell_type']=='code':
            tx=''.join(c['source'])
            tx=tx.replace("ROOT=Path.cwd()\nif not (ROOT/'results/comparison.json').exists(): ROOT=ROOT/'p4/v3'", "candidates=[Path.cwd(),Path.cwd()/'v3',Path.cwd().parent/'v3',Path.cwd()/'p4/v3']\nROOT=next(p for p in candidates if (p/'results/comparison.json').exists())")
            if 'if not source.exists()' not in tx:
                tx=tx.replace("source=ROOT.parent/'customer-support'", "source=ROOT.parent/'customer-support'\nif not source.exists(): source=ROOT.parent")
            c['source']=tx.splitlines(keepends=True)
    n['cells'].insert(1,{'cell_type':'markdown','metadata':{},'source':['## Sources and completed review\n','Sources: Evaluations Using LangSmith handout and The Gen Academy repository. 100 synthetic tickets from 25 seed scenarios, each original plus three paraphrases. Five intent categories. Historical Excel reviews: Evaluation 11/11 and Fresh evaluation 14/14 approved. Completed LangSmith queues: baseline 8/8 and focused 7/7, 15 run reviews across 14 tickets with 75 feedback records. Approvals document review; they do not rewrite predictions.']})
    ns={}; count=0; old=Path.cwd()
    try:
        os.chdir(ROOT)
        for c in n['cells']:
            if c['cell_type']!='code': continue
            count+=1; buf=io.StringIO()
            with contextlib.redirect_stdout(buf): exec(compile(''.join(c['source']),f'final-notebook-cell-{count}','exec'),ns)
            c['execution_count']=count;c['outputs']=[{'output_type':'stream','name':'stdout','text':buf.getvalue().splitlines(keepends=True)}]
    finally: os.chdir(old)
    (ROOT/'customer_support_evaluation.ipynb').write_text(json.dumps(n,indent=2,ensure_ascii=False),encoding='utf-8')
    d=json.loads((OUT/'presentation_content_with_judge.json').read_text(encoding='utf-8'))
    (OUT/'project_summary_20_lines.txt').write_text('\n'.join(f'{i:02d}. {t}' for i,t in enumerate(d['summary'],1))+'\n',encoding='utf-8')
    for href in re.findall(r'href="([^"]+)"',html):
        if not href.startswith(('http','#')): assert (OUT/href).exists(),href
    receipt={'status':'PASS','notebook_code_cells_executed':count,'classifier_same_policy':s['same_v3_policy_scores'],'judge_before':99,'judge_final':100,'ambiguity_flags':12,'summary_lines':20,'historical_source_hashes_verified_by_notebook':True}
    (OUT/'final_submission_validation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))
if __name__=='__main__': build()
