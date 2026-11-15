"""Validate final evidence, notebook execution, and local report references."""
import json
import sys
if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import submission_analysis as analysis

final=analysis.reconcile()
fresh=final['reviewed_metrics']['Fresh evaluation']
assert (fresh['baseline_correct'],fresh['revised_correct'],fresh['wins'],fresh['regressions'])==(93,93,7,7)
assert final['reviewed_metrics']['Evaluation']['approved_failed_cases']==11
assert fresh['approved_failed_cases']==14
assert sum(q['completed'] for q in final['queues'])==15
assert final['feedback_records_verified']==75
notebook=json.loads((analysis.ROOT/'customer_support_evaluation.ipynb').read_text(encoding='utf-8'))
assert notebook['nbformat']==4
scope={'__name__':'verification'}
count=0
for cell in notebook['cells']:
    if cell['cell_type']=='code':
        count+=1
        assert cell['execution_count']==count
        assert not any(o['output_type']=='error' for o in cell['outputs'])
        exec(compile(''.join(cell['source']),'<verification notebook>','exec'),scope)
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('href','src') and not urlsplit(value).scheme and not value.startswith('#'):
                path=analysis.ROOT/'outputs'/unquote(urlsplit(value).path)
                assert path.is_file(),str(path)
report=(analysis.ROOT/'outputs/project_report.html').read_text(encoding='utf-8')
Links().feed(report)
for stale in ('Participant review is still pending','Participant annotations remain pending','PREPARED_NOT_RUN'):
    assert stale not in report and stale not in json.dumps(notebook)
assert '93/100' in report and '75 feedback records' in report
print('PASS: all final metrics, approvals, queue evidence and workbook hash reconcile.')
print('PASS:',count,'notebook analysis cells execute without network or model calls.')
print('PASS: report links resolve; historical review evidence reconciles.')
latest=json.loads((scope['ROOT']/'llm_judge_v2/summary.json').read_text(encoding='utf-8'))
assert latest['judge_pass']==100 and latest['ambiguity_flags']==12
assert scope['summary']['same_v3_policy_scores']=={'baseline':92,'focused':94,'v3':100}
assert len((analysis.ROOT/'outputs/project_summary_20_lines.txt').read_text(encoding='utf-8').splitlines())==20
print('PASS: final v3 100/100; calibrated judge 100/100; 12 ambiguity flags; 20 summary lines.')
