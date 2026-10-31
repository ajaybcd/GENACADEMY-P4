"""Package a whitelist of final deliverables; never include saved credentials."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import submission_analysis as analysis

root=analysis.ROOT
final=analysis.reconcile()
names=['README.md','project.py','submission_analysis.py','finalize_submission.py','build_deliverables.py','verify_submission.py',
    'sync_annotation_queues.py','credentials.ps1','.env.example','requirements.txt','customer_support_evaluation.ipynb','walkthrough_script.txt',
    'outputs/project_report.html','outputs/customer_support_evaluation.xlsx','outputs/final_review_snapshot.json',
    'outputs/final_fresh_run_reviews.csv','outputs/final_saved_run_reviews.csv','outputs/langsmith_dataset.csv','outputs/source_manifest.json',
    'qa/langsmith-notes-and-approval.png','qa/langsmith-approved-field.png']
for directory in ('prompts','source','live_runs','outputs/langsmith_annotation_sync'):
    names.extend(p.relative_to(root).as_posix() for p in (root/directory).iterdir() if p.is_file() and p.suffix in ('.txt','.csv','.json','.md','.ipynb'))
names=sorted(set(names))
files=[]
for name in names:
    path=(root/name).resolve()
    assert path.is_relative_to(root) and path.is_file(),name
    assert not any(part in ('.venv','node_modules','.credentials.local.json','.env') for part in Path(name).parts)
    raw=path.read_bytes()
    if path.suffix in ('.py','.ps1','.json','.txt','.md','.csv','.ipynb'):
        text=raw.decode('utf-8-sig')
        if re.search(r'(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|lsv2_pt_[A-Za-z0-9_]{20,})',text):raise ValueError('Possible credential in '+name)
    files.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
manifest={'review_status':'All failed-case worksheet reviews approved','langsmith_status':'8 baseline and 7 focused completed; 75 feedback records verified',
    'reviewed_fresh_scores':'93/100 baseline and 93/100 focused; 7 wins, 7 regressions',
    'remaining_participant_action':'Record Loom walkthrough and supply its actual link to the course submission',
    'files':files}
(root/'outputs/submission_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
destination=root.parent/'customer_support_submission.zip'
with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
    for name in names:archive.write(root/name,'customer-support/'+name)
    archive.write(root/'outputs/submission_manifest.json','customer-support/outputs/submission_manifest.json')
with ZipFile(destination) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist())==len(names)+1
    assert not any('.credentials.local.json' in name or '/.venv/' in name or '/node_modules/' in name for name in archive.namelist())
print('Submission archive verified:',destination)
print('Files:',len(names)+1,'Bytes:',destination.stat().st_size)
print('Loom recording/link remains the participant submission step.')
