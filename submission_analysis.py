"""Read-only reconciliation of the approved workbook and LangSmith evidence."""
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def read_workbook():
    with ZipFile(ROOT/'outputs/customer_support_evaluation.xlsx') as archive:
        strings=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheets=ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets',NS)
        def value(cell):
            raw=cell.find('s:v',NS)
            return strings[int(raw.text)] if cell.attrib.get('t')=='s' else raw.text if raw is not None else ''.join(cell.itertext())
        result={}
        for index,sheet in enumerate(sheets,1):
            name=sheet.attrib['name']
            if name not in ('Evaluation','Fresh evaluation'):continue
            records=[]
            for row in ET.fromstring(archive.read(f'xl/worksheets/sheet{index}.xml')).findall('.//s:sheetData/s:row',NS):
                c={''.join(filter(str.isalpha,x.attrib['r'])):value(x) for x in row}
                if not c.get('A','').startswith('t') or not c.get('B'):continue
                a=c.get('E')==c.get('D');b=c.get('G')==c.get('D')
                change='WIN' if not a and b else 'REGRESSION' if a and not b else 'STILL_PASS' if b else 'STILL_FAIL'
                records.append({'sheet':name,'row':int(row.attrib['r']),'id':c['A'],'query':c['B'],
                    'source_intent':c.get('C',''),'reviewed_intent':c.get('D',''),'baseline_prediction':c.get('E',''),'revised_prediction':c.get('G',''),
                    'baseline_exact_match':int(a),'revised_exact_match':int(b),'change':change,'failure_category':c.get('J',''),
                    'ai_draft_note':c.get('K',''),'participant_note':c.get('L',''),'participant_approval':c.get('M','')})
            result[name]=records
    return result

def metrics(rows):
    failed=[r for r in rows if not r['baseline_exact_match'] or not r['revised_exact_match']]
    return {'tickets':len(rows),'baseline_correct':sum(r['baseline_exact_match'] for r in rows),'revised_correct':sum(r['revised_exact_match'] for r in rows),
        'delta_percentage_points':100*sum(r['revised_exact_match']-r['baseline_exact_match'] for r in rows)/len(rows),
        **{k:sum(r['change']==v for r in rows) for k,v in [('wins','WIN'),('regressions','REGRESSION'),('still_pass','STILL_PASS'),('still_fail','STILL_FAIL')]},
        'failed_cases':len(failed),'approved_failed_cases':sum(r['participant_approval']=='Approved' for r in failed),
        'pending_failed_cases':sum(r['participant_approval']!='Approved' for r in failed)}

def reconcile():
    sheets=read_workbook()
    evidence=json.loads((ROOT/'live_runs/langsmith_evidence.json').read_text(encoding='utf-8'))
    sync=json.loads((ROOT/'outputs/langsmith_annotation_sync/sync_evidence.json').read_text(encoding='utf-8'))
    plan=json.loads((ROOT/'outputs/langsmith_annotation_sync/review_transfer_plan.json').read_text(encoding='utf-8'))
    original={}
    for version,name in zip(('baseline','focused'),evidence['experiments']):
        rows=read_csv(ROOT/'live_runs'/f'{name}.csv')
        if len(rows)!=100 or len({r['id'] for r in rows})!=100 or any(r['error'] for r in rows):raise ValueError('Incomplete source run')
        original[version]={'correct':sum(r['prediction']==r['reference_intent'] for r in rows),'tickets':len(rows),'errors':0}
        indexed={r['id']:r for r in rows}
        for reviewed in sheets['Fresh evaluation']:
            raw=indexed[reviewed['id']]
            if raw['query']!=reviewed['query'] or raw['prediction']!=reviewed['baseline_prediction' if version=='baseline' else 'revised_prediction']:raise ValueError('Original prediction or query changed')
    reviewed_metrics={name:metrics(rows) for name,rows in sheets.items()}
    if any(m['pending_failed_cases'] for m in reviewed_metrics.values()):raise ValueError('Failure approval pending')
    if not sync.get('verified') or sync['verified_feedback_records']!=len(sync['records'])*5:raise ValueError('Feedback verification incomplete')
    if any(q['completed']!=q['expected'] or q['needs_my_review']!=0 for q in sync['queues']):raise ValueError('Queue completion incomplete')
    current_hash=hashlib.sha256((ROOT/'outputs/customer_support_evaluation.xlsx').read_bytes()).hexdigest()
    if current_hash!=sync['workbook_sha256']:raise ValueError('Workbook changed after annotation transfer')
    queues=[{**q,'url':'https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/a/-/annotation-queues/'+q['id']+'?runView=completed'} for q in sync['queues']]
    return {'workbook_sha256':current_hash,'original_fresh_runs':original,'reviewed_metrics':reviewed_metrics,
        'label_changes':[{'id':r['id'],'source_intent':r['source_intent'],'reviewed_intent':r['reviewed_intent']} for r in sheets['Fresh evaluation'] if r['source_intent']!=r['reviewed_intent']],
        'queues':queues,'feedback_records_verified':sync['verified_feedback_records'],'queue_run_reviews':len(sync['records']),'unique_queue_tickets':sync['unique_tickets'],
        'notes_from_column_k':[r['ticket_id'] for r in plan['records'] if r['note_source_column']=='K'],
        'langsmith_evidence':evidence,'loom_status':'Recording and actual link still required from participant','optional_llm_judge':'Not attempted; optional','workbook_rows':sheets}

def save_snapshot():
    result=reconcile()
    (ROOT/'outputs/final_review_snapshot.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for name,filename in [('Evaluation','final_saved_run_reviews.csv'),('Fresh evaluation','final_fresh_run_reviews.csv')]:
        rows=result['workbook_rows'][name]
        with (ROOT/'outputs'/filename).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return result
