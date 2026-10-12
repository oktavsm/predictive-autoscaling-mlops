#!/usr/bin/env python3
"""Create and verify the portable kit archive, without third-party packages."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
archive = root / 'titipin-mlops-design-kit-v1.1.0.zip'
def excluded(path):
    return path.name == 'MANIFEST.json' or path.suffix == '.zip' or path.name.endswith('.zip.sha256') or '__pycache__' in path.parts

files = sorted(p for p in root.rglob('*') if p.is_file() and not excluded(p))
manifest = {'kit':'Titipin MLOps','version':'1.1.0','algorithm':'sha256','exclusions':['MANIFEST.json (self)','*.zip','*.zip.sha256','__pycache__'], 'files':[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
(root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files+[root/'MANIFEST.json']:
        info=zipfile.ZipInfo('titipin-mlops-design-kit/'+p.relative_to(root).as_posix(),date_time=(2026,10,12,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o644<<16
        z.writestr(info,p.read_bytes())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for entry in manifest['files']:
        data=z.read('titipin-mlops-design-kit/'+entry['path'])
        assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    assert len(z.namelist())==len(files)+1
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(root/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
print(f'Verified {len(files)} payload hashes + manifest. ZIP: {archive.stat().st_size:,} bytes. SHA-256 {digest}')
