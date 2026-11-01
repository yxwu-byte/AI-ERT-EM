"""Package a tested worker, with a complete SHA256 file manifest."""
import hashlib,json,sys,zipfile,os
from pathlib import Path
engine,folder,archive=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
manifest=dict(engine=engine,protocol=1,version='0.3.0',platform='windows-x64' if os.name=='nt' else 'linux-x64',
              files={str(path.relative_to(folder)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in folder.rglob('*') if path.is_file() and path.name!='engine.json'})
(folder/'engine.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
archive.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as target:
    for path in folder.rglob('*'):
        if path.is_file():target.write(path,str(path.relative_to(folder)).replace('\\','/'))
print(archive,archive.stat().st_size)
