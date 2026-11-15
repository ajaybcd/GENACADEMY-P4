"""Create presentation scripts from the final, participant-reviewed evidence."""
import json, re
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'
MAIN = [
('1 • Introduction', 'My project evaluates an AI customer support classifier. The goal is to route an incoming ticket to the right support category and understand why routing fails. I compared a baseline prompt with one focused change, then reviewed the failures and recorded my decisions in Excel and LangSmith.'),
('2 • Task and sources', 'The project follows the Evaluations Using LangSmith handout and the Gen Academy customer support evaluation repository. The dataset contains one hundred synthetic e-commerce tickets across five intents: order status, refund request, product issue, account help, and other. These are twenty-five seed scenarios with paraphrases, so they are not one hundred independent real customer cases.'),
('3 • Evaluation method', 'OpenAI GPT-4o-mini classified each ticket using a structured intent response. A code-based Exact Match evaluator compared the prediction with the reference label. LangSmith stored the experiments and traces. Two runs produced two hundred predictions. The evaluation and later annotation steps did not require additional model calls.'),
('4 • What went wrong', 'The baseline sometimes followed the requested remedy rather than the underlying problem. For example, a customer whose parcel never arrived might ask for a refund. The classifier could select refund request when the original reference expected order status. Damaged-product tickets created a similar conflict between the problem and the requested refund.'),
('5 • The focused change', 'I tested one additional routing-precedence instruction. It told the model to classify the underlying problem first: non-delivery as order status, and damaged or defective items as product issue, even when a refund was requested. This helped targeted cases, but it also caused confusion when a returned item’s refund payment had not arrived.'),
('6 • My review and annotations', 'I reviewed the failure cases, used AI-assisted explanations, added or confirmed notes in column L, and approved reviews in column M. I also changed ticket t046’s reference label from product issue to refund request. The saved model predictions stayed intact. All eleven failure cases in the older Evaluation tab and fourteen in Fresh evaluation are approved. The fresh reviews were transferred to LangSmith: eight baseline runs and seven focused runs, representing fourteen distinct tickets. All fifteen run reviews are completed, with seventy-five feedback records verified.'),
('7 • Before and after', 'With the original labels, the fresh baseline scored ninety-two percent and the focused prompt scored ninety-four percent. After my reference correction, both were rescored against the same reviewed labels and both scored ninety-three percent. There were seven improvements and seven regressions, so the final net gain was zero. Approval means I reviewed the case; it does not change an incorrect prediction into a correct one.'),
('8 • Conclusion', 'The project improved visibility into failures and created an auditable review trail, but the final reviewed accuracy did not improve. My main observation is that routing policy and reference-label consistency matter as much as prompt wording. Next, I would clarify refund-versus-problem precedence and test on independent tickets. The report, notebook, workbook, and annotation evidence are published on GitHub; the remaining submission step is to record the walkthrough and add its link.')
]
DEMO = [
('0:00–0:15 • Open the final report', 'Here is the final report. This project routes one hundred customer support tickets into five categories. I compared two prompts using OpenAI predictions and Exact Match evaluation in LangSmith.'),
('0:15–0:35 • Show Fresh evaluation in Excel', 'In the workbook, column L contains review notes and column M records approval. These decisions document my review, while the saved model predictions remain unchanged. All fourteen fresh failure cases are approved.'),
('0:35–0:48 • Show Fresh evaluation!D52, ticket t046', 'For ticket t046, I changed the reference from product issue to refund request. That correction is why the final reviewed scores differ from the original experiment scores.'),
('0:48–1:12 • Show both LangSmith queues, Completed view', 'In LangSmith, the baseline queue has eight completed runs and the focused queue has seven. Opening a run shows the transferred notes, failure category, reviewed intent, approval, and reviewed Exact Match. These are fifteen run reviews across fourteen tickets.'),
('1:12–1:30 • Return to results; show GitHub', 'The original scores were ninety-two and ninety-four percent. Under the reviewed labels, both are ninety-three percent: seven wins and seven regressions. There is no net accuracy improvement. GitHub contains the report, notebook, workbook, and supporting evidence.')
]
SUMMARY = [
'The project evaluates AI routing of customer support tickets into five intent categories.',
'The aim is to identify routing failures and test one focused prompt change.',
'Sources are the LangSmith handout and the Gen Academy customer support evaluation repository.',
'The dataset has 100 synthetic tickets derived from 25 seed scenarios and their paraphrases.',
'The intents are order_status, refund_request, product_issue, account_help, and other.',
'OpenAI gpt-4o-mini generated 100 baseline and 100 focused-prompt predictions.',
'A code-based Exact Match evaluator scored predictions against reference labels.',
'LangSmith stored the experiments, traces, annotation queues, and review feedback.',
'Baseline failures often prioritized a requested refund over the underlying customer problem.',
'One added instruction prioritized non-delivery and product problems over the refund remedy.',
'I reviewed AI-assisted explanations, added or confirmed Excel notes, and approved failure reviews.',
'The older Evaluation tab has 11/11 approved failure cases; Fresh evaluation has 14/14.',
'I changed t046’s reference from product_issue to refund_request without changing predictions.',
'Original fresh-run accuracy was 92% baseline and 94% focused: a two-point increase.',
'After applying the reviewed label consistently, both versions scored 93%: no net increase.',
'Seven corrected cases were offset by seven regressions, exposing ambiguity in refund routing.',
'LangSmith has 15 completed run reviews for 14 tickets and 75 verified feedback records.',
'The project is published on GitHub; next steps are independent testing and the recorded walkthrough.'
]

content_override=OUT/'presentation_content_with_judge.json'
if content_override.exists():
    integrated=json.loads(content_override.read_text(encoding='utf-8'))
    MAIN=integrated['main']; DEMO=integrated['demo']; SUMMARY=integrated['summary']

data = {'main': MAIN, 'demo': DEMO, 'summary': SUMMARY,
        'main_words': sum(len(re.findall(r"\b[\w’-]+\b", p)) for _, p in MAIN),
        'demo_words': sum(len(re.findall(r"\b[\w’-]+\b", p)) for _, p in DEMO)}
(ROOT/'qa'/'presentation_content.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

doc = Document()
sec=doc.sections[0]
sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.65)
sec.left_margin=Inches(.8); sec.right_margin=Inches(.8)
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
for name in ('Normal','Title','Subtitle','Heading 1','Heading 2'):
    st=doc.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)
    st.font.size=Pt(11.5 if name=='Normal' else {'Title':25,'Subtitle':11,'Heading 1':17,'Heading 2':12}[name])
    st.paragraph_format.space_after=Pt(7)
    st.paragraph_format.line_spacing=1.10
doc.styles['Heading 2'].paragraph_format.space_before=Pt(9)
doc.styles['Normal'].paragraph_format.widow_control=True

def p(text, style=None): return doc.add_paragraph(text, style)
def title(text,sub):
    p(text,'Title'); p(sub,'Subtitle')

title('Customer support intent evaluation', 'Ajay David • Week 4, Project 4 • Presentation transcript')
p('Main narration | About 3–4 minutes','Heading 1')
p(f'{data["main_words"]} spoken words. Read at about 135–150 words per minute; rehearse once with slide changes. Headings are cues, not spoken text.')
for h,tx in MAIN[:4]: p(h,'Heading 2');p(tx)
doc.add_page_break()
title('Main narration continued', 'Slides 5–9 • Results, review and LLM judge')
for h,tx in MAIN[4:]:p(h,'Heading 2');p(tx)
doc.add_page_break()
title('Live demo transcript', 'About 1½ minutes • Open the files and LangSmith queues before recording')
p(f'{data["demo_words"]} spoken words. The timings include short pauses for screen changes. Speak only the paragraphs; use headings as action cues.')
for h,tx in DEMO:p(h,'Heading 2');p(tx)
p('Demo preparation','Heading 1')
p('Open project_report.html, the highlighted v3_evaluation_review.xlsx workbook, the executed notebook, and the LangSmith v3 comparison. Use Changes to review and Judge v2 review. Keep the separate t033 human review and original rubric-v1 result available. The historical workbook retains the original notes and approvals. Do not rerun models during the demo.')
p('Useful links','Heading 2')
p('GitHub: https://github.com/ajaybcd/GENACADEMY-P4')
p('LangSmith queue links are in the final report and in the PowerPoint speaker notes.')
doc.add_page_break()
title('Project summary', f'{len(SUMMARY)} concise points • Submission and speaking reference')
for i,tx in enumerate(SUMMARY,1):
    para=p(f'{i:02d}.  {tx}');para.paragraph_format.space_after=Pt(6)
p('Evidence: v3/results/comparison.json, v3/llm_judge_v2/before_after.json and verified LangSmith feedback. The historical snapshot and original automated judgments remain preserved.','Subtitle')
if content_override.exists():
    doc.add_page_break()
    title('Final v3 and LLM judge analysis', 'Known dataset results and separately preserved human review')
    for h,tx in integrated['judge_appendix']: p(h,'Heading 2');p(tx)

foot=sec.footer.paragraphs[0];foot.alignment=2
run=foot.add_run('Week 4 • P4   |   ');run.font.size=Pt(9)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)
doc.core_properties.title='Customer support evaluation: narration, demo and summary'
doc.core_properties.author='Ajay David'
doc.core_properties.subject='Final reviewed results and completed LangSmith annotations'
dest=OUT/'project_transcript_and_summary.docx';doc.save(dest)
print(json.dumps({'docx':str(dest),'main_words':data['main_words'],'demo_words':data['demo_words']}))
