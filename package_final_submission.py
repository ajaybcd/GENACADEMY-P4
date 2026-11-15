"""Package the latest saved submission without credentials or local runtimes."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json,re
from final_submission import ROOT,build
build()
manifest=json.loads((ROOT/'outputs/submission_manifest.json').read_text(encoding='utf-8'))
destination=ROOT.parent/'customer_support_submission.zip' if ROOT.name=='customer-support' else ROOT/'customer_support_submission.zip'
with ZipFile(destination,'w',ZIP_DEFLATED) as z:
    for entry in manifest['files']:
        name=entry['path'];src=ROOT/name
        if not src.exists() and name.startswith(('v3/','llm-judge/')):src=ROOT.parent/name
        assert src.is_file(),name
        assert not any(x in Path(name).parts for x in ['.credentials.local.json','.venv','node_modules','.git'])
        if src.suffix in ['.json','.txt','.py','.ps1','.csv','.ipynb','.html','.md']:
            assert not re.search(r'(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|lsv2_pt_[A-Za-z0-9_]{20,})',src.read_text(encoding='utf-8-sig')),name
        z.write(src,name)
    z.write(ROOT/'outputs/submission_manifest.json','outputs/submission_manifest.json')
with ZipFile(destination) as z:assert z.testzip() is None
print(destination)
