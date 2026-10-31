"""Transfer explicitly approved Excel reviews to matching saved LangSmith runs."""
import argparse
import asyncio
import csv
import hashlib
import json
from pathlib import Path
import uuid
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
WORKBOOK=ROOT/'outputs/customer_support_evaluation.xlsx'
OUT=ROOT/'outputs/langsmith_annotation_sync'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CATEGORIES=['Requested remedy overrides underlying problem','Refund payment confused with order delivery','Reference label policy disagreement']
KEYS={'category':'failure_category','notes':'week4_p4_review_notes','approval':'week4_p4_workbook_approved','reference':'week4_p4_reviewed_intent','exact':'week4_p4_reviewed_exact_match'}

def workbook_rows():
    with ZipFile(WORKBOOK) as archive:
        strings=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in archive.namelist() else []
        sheets=ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets',NS)
        index=next(i+1 for i,s in enumerate(sheets) if s.attrib['name']=='Fresh evaluation')
        tree=ET.fromstring(archive.read(f'xl/worksheets/sheet{index}.xml'))
        def value(cell):
            raw=cell.find('s:v',NS)
            if cell.attrib.get('t')=='s': return strings[int(raw.text)]
            return raw.text if raw is not None else ''.join(cell.itertext())
        rows=[]
        for row in tree.findall('.//s:sheetData/s:row',NS):
            record={''.join(filter(str.isalpha,c.attrib['r'])):value(c) for c in row}
            if record.get('A','').startswith('t') and record.get('B'):
                rows.append({**record,'row':int(row.attrib['r'])})
        return rows

def plan():
    evidence=json.loads((ROOT/'live_runs/langsmith_evidence.json').read_text(encoding='utf-8'))
    records=[]
    for version,experiment in zip(('baseline','focused'),evidence['experiments']):
        with (ROOT/'live_runs'/f'{experiment}.csv').open(encoding='utf-8-sig',newline='') as stream:
            index={r['id']:r for r in csv.DictReader(stream)}
        for row in workbook_rows():
            source=index[row['A']]
            if source['query']!=row['B'] or source['prediction']!=row['E' if version=='baseline' else 'G']:
                raise ValueError('Workbook and saved model evidence do not match '+row['A'])
            original_fail=source['prediction']!=source['reference_intent']
            reviewed_fail=source['prediction']!=row['D']
            if not (original_fail or reviewed_fail): continue
            if row.get('M')!='Approved': raise ValueError('Case lacks explicit approval: '+row['A'])
            notes=row.get('L','').strip() or row.get('K','').strip()
            note_source_column='L' if row.get('L','').strip() else 'K'
            if not notes: raise ValueError('Case lacks a review note: '+row['A'])
            label_changed=source['reference_intent']!=row['D']
            category='Reference label policy disagreement' if label_changed else row['J']
            if category not in CATEGORIES: raise ValueError('Unsupported category '+category)
            records.append({'version':version,'experiment':experiment,'ticket_id':row['A'],'workbook_row':row['row'],
                'run_id':source['run_id'],'query':row['B'],'prediction':source['prediction'],
                'original_reference_intent':source['reference_intent'],'reviewed_reference_intent':row['D'],
                'original_exact_match':int(not original_fail),'reviewed_exact_match':int(not reviewed_fail),
                'failure_category':category,'workbook_category':row['J'],'review_notes':notes,'note_source_column':note_source_column,'approval':'Approved',
                'provenance':'Participant approved this Excel row in column M. Notes imported from column '+note_source_column+'; column K is the original AI-assisted draft when column L is empty. Imported via API.'})
    OUT.mkdir(exist_ok=True)
    payload={'workbook_sha256':hashlib.sha256(WORKBOOK.read_bytes()).hexdigest(),'source_sheet':'Fresh evaluation',
        'unmapped_source_tab':'Evaluation contains older repository-only results without matching live run IDs; not imported.',
        'records':records,'planned_run_count':len(records),'unique_tickets':len({r['ticket_id'] for r in records})}
    (OUT/'review_transfer_plan.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload

async def sync(payload):
    from langsmith import Client
    client=Client()
    # Validate every live run before writing queue entries or feedback.
    actual_runs={}
    for row in payload['records']:
        run=client.read_run(row['run_id'])
        if run.inputs.get('query')!=row['query'] or (run.outputs or {}).get('intent')!=row['prediction']:
            raise ValueError('Remote run evidence mismatch '+row['ticket_id'])
        actual_runs[row['run_id']]=run
    configs={KEYS['category']:{'type':'categorical','categories':[{'value':i,'label':v} for i,v in enumerate(CATEGORIES)]},
        KEYS['notes']:{'type':'freeform'},KEYS['approval']:{'type':'categorical','categories':[{'value':1,'label':'Approved'},{'value':0,'label':'Needs change'}]},
        KEYS['reference']:{'type':'freeform'},KEYS['exact']:{'type':'continuous','min':0,'max':1}}
    for key,config in configs.items():
        existing=list(client.list_feedback_configs(feedback_key=[key]))
        if existing:
            raw=existing[0].feedback_config
            if hasattr(raw,'model_dump'): raw=raw.model_dump(exclude_none=True)
            if dict(raw)!=config: raise ValueError('Existing feedback config differs; refusing to overwrite '+key)
        else: client.create_feedback_config(key,feedback_config=config)
    result={'workbook_sha256':payload['workbook_sha256'],'unique_tickets':payload['unique_tickets'],'queues':[],'records':[]}
    for version in ('baseline','focused'):
        subset=[r for r in payload['records'] if r['version']==version]
        queue_name='Week4 P4 '+version+' approved Excel reviews'
        queues=list(client.list_annotation_queues(name=queue_name))
        if len(queues)>1: raise ValueError('Multiple queues have the same name.')
        if queues: queue=client.read_annotation_queue(queues[0].id)
        else:
            queue=client.create_annotation_queue(name=queue_name,
                description='Approved Excel reviews mapped to original '+version+' runs. Includes original errors and reviewed-label errors. No new model calls.',
                rubric_instructions='Reviews were completed and approved in Excel. Imported notes retain their origin. failure_category describes the mechanism. Original run predictions and experiment feedback are preserved. A corrected reference is stored in a separate reviewed-intent field.',
                rubric_items=[{'feedback_key':key,'is_required':True,'description':desc} for key,desc in [
                    (KEYS['notes'],'Participant-approved workbook explanation'),(KEYS['category'],'Main failure mechanism, or reference-label policy disagreement'),
                    (KEYS['approval'],'Review approval imported from column M'),(KEYS['reference'],'Reviewed workbook reference label'),(KEYS['exact'],'Prediction matches the reviewed reference')]])
        # Add only missing runs to avoid duplicates on a retry.
        queue_items=[]
        for status in ('needs_my_review','needs_others_review','archived'):
            queue_items.extend([i async for i in client.annotation_queues.items.list(str(queue.id),status=status,page_size=100)])
        present={str(i.run_id) for i in queue_items}
        missing=[r for r in subset if r['run_id'] not in present]
        if missing:
            response=await client.annotation_queues.items.create(str(queue.id),extend_trace_retention=False,items=[{
                'item_type':'RUN','run_id':r['run_id'],'project_id':str(actual_runs[r['run_id']].session_id),'start_time':actual_runs[r['run_id']].start_time} for r in missing])
            queue_items.extend(response.items or [])
        mapped={str(i.run_id):i for i in queue_items}
        for row in subset:
            source={'workbook_sha256':payload['workbook_sha256'],'source_sheet':'Fresh evaluation','source_row':row['workbook_row'],
                'ticket_id':row['ticket_id'],'provenance':row['provenance'],'note_source_column':row['note_source_column'],'original_reference_intent':row['original_reference_intent'],
                'workbook_category':row['workbook_category']}
            values=[(KEYS['notes'],None,row['review_notes']),
                    (KEYS['category'],CATEGORIES.index(row['failure_category']),row['failure_category']),
                    (KEYS['approval'],1,'Approved'),(KEYS['reference'],None,row['reviewed_reference_intent']),
                    (KEYS['exact'],row['reviewed_exact_match'],None)]
            existing={str(f.id):f for f in client.list_feedback(run_ids=[row['run_id']],feedback_key=list(KEYS.values()))}
            feedback_ids=[]
            for key,score,value in values:
                fid=str(uuid.uuid5(uuid.NAMESPACE_URL,'week4-p4-excel-review/'+row['run_id']+'/'+key))
                if fid not in existing:
                    client.create_feedback(run_id=row['run_id'],key=key,score=score,value=value,
                        comment='Imported approved Excel review. '+row['review_notes'] if key==KEYS['category'] else 'Imported from Fresh evaluation row '+str(row['workbook_row'])+'.',
                        source_info=source,feedback_source_type='api',feedback_id=fid)
                feedback_ids.append(fid)
            # This completion transfers the user's explicit Approved in Excel.
            item=mapped[row['run_id']]
            await client.annotation_queues.items.create_status(str(item.id),status='completed')
            result['records'].append({'ticket_id':row['ticket_id'],'version':version,'run_id':row['run_id'],
                'queue_item_id':str(item.id),'feedback_ids':feedback_ids,'approval':'Approved'})
            (OUT/'sync_evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        complete=[i async for i in client.annotation_queues.items.list(str(queue.id),status='archived',page_size=100)]
        needs=[i async for i in client.annotation_queues.items.list(str(queue.id),status='needs_my_review',page_size=100)]
        result['queues'].append({'version':version,'name':queue_name,'id':str(queue.id),'expected':len(subset),'completed':len(complete),'needs_my_review':len(needs)})
        print(json.dumps(result['queues'][-1]),flush=True)
        (OUT/'sync_evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    # Read back all five feedback values for all runs; verify exact notes and labels.
    for row in payload['records']:
        feedback={str(f.id):f for f in client.list_feedback(run_ids=[row['run_id']],feedback_key=list(KEYS.values()))}
        for key in KEYS.values():
            fid=str(uuid.uuid5(uuid.NAMESPACE_URL,'week4-p4-excel-review/'+row['run_id']+'/'+key))
            if fid not in feedback: raise ValueError('Missing readback feedback '+row['ticket_id']+' '+key)
        noteid=str(uuid.uuid5(uuid.NAMESPACE_URL,'week4-p4-excel-review/'+row['run_id']+'/'+KEYS['notes']))
        if feedback[noteid].value!=row['review_notes']: raise ValueError('Imported note mismatch')
    result['verified_feedback_records']=len(payload['records'])*5
    result['verified']=True
    (OUT/'sync_evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--apply',action='store_true'); args=parser.parse_args()
    payload=plan()
    if args.apply: print(json.dumps(asyncio.run(sync(payload)),indent=2))
    else: print(json.dumps({k:v for k,v in payload.items() if k!='records'},indent=2))
