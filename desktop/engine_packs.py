"""Optional self-contained solver packs; the base installer never needs their libraries."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile
from runtime import configure_runtime

ENGINES={'pygimli':'pyGIMLi','simpeg':'SimPEG','hydro':'PyHydroGeophysX'}
PROTOCOL=1
PACK_PAGE='https://github.com/yxwu-byte/AI-ERT-EM/pull/2'


def engine_path(engine):
    if engine not in ('simpeg','hydro'):
        raise ValueError('Only SimPEG and PyHydroGeophysX use optional packs.')
    folder=configure_runtime()/'engines'/engine
    exe=folder/('ERTEngine.exe' if os.name=='nt' else 'ERTEngine')
    manifest=folder/'engine.json'
    try:
        info=json.loads(manifest.read_text(encoding='utf-8'))
        if info['engine']!=engine or info['protocol']!=PROTOCOL or not exe.is_file():
            return None
    except (OSError,ValueError,KeyError):
        return None
    return exe


def install_pack(archive):
    destination=configure_runtime()/'engines'
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ert-pack-',dir=destination) as temporary:
        staging=Path(temporary)/'payload'; staging.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            infos=zipped.infolist()
            if len(infos)>20000 or sum(item.file_size for item in infos)>2*1024**3:
                raise ValueError('Engine pack is too large.')
            for item in infos:
                name=item.filename
                path=PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or (item.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('Unsafe engine pack path.')
            if len({item.filename for item in infos})!=len(infos):
                raise ValueError('Duplicate archive entries.')
            try:
                manifest=json.loads(zipped.read('engine.json'))
            except (KeyError,ValueError) as exc:
                raise ValueError('Select the engine-pack ZIP, not the outer GitHub artifact ZIP. Extract the artifact first.') from exc
            engine=manifest.get('engine')
            if engine not in ('simpeg','hydro') or manifest.get('protocol')!=PROTOCOL:
                raise ValueError('Incompatible or unknown engine pack.')
            if manifest.get('platform') != ('windows-x64' if os.name=='nt' else 'linux-x64'):
                raise ValueError('This engine pack is for a different operating system.')
            files=manifest.get('files',{})
            actual={item.filename for item in infos if not item.is_dir() and item.filename!='engine.json'}
            if not isinstance(files,dict) or actual!=set(files):
                raise ValueError('Engine pack file manifest mismatch.')
            executable='ERTEngine.exe' if os.name=='nt' else 'ERTEngine'
            if executable not in files:
                raise ValueError('Pack does not contain a worker executable.')
            for item in infos:
                if item.is_dir():
                    continue
                target=staging/item.filename
                target.parent.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256()
                with zipped.open(item) as source,target.open('wb') as output:
                    while chunk:=source.read(1024*1024):
                        digest.update(chunk);output.write(chunk)
                if item.filename!='engine.json' and digest.hexdigest()!=files[item.filename]:
                    raise ValueError(f'Engine pack integrity check failed: {item.filename}')
            if os.name!='nt': (staging/executable).chmod(0o755)
        target=destination/engine
        backup=destination/(engine+'.previous')
        if backup.exists(): shutil.rmtree(backup)
        if target.exists(): target.rename(backup)
        try:
            staging.rename(target)
        except OSError:
            if backup.exists(): backup.rename(target)
            raise
        if backup.exists(): shutil.rmtree(backup)
    return engine
