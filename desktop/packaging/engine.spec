from pathlib import Path
import os,json
from PyInstaller.utils.hooks import collect_all,collect_data_files,copy_metadata,collect_delvewheel_libs_directory
root=Path(SPECPATH).parent
engine=os.environ['ERT_ENGINE']
if engine not in ('simpeg','hydro'):raise ValueError('Set ERT_ENGINE to simpeg or hydro')
info=root.parent/'build'/'engine-info'/engine
info.mkdir(parents=True,exist_ok=True)
(info/'engine-id.json').write_text(json.dumps({'engine':engine}))
datas=[(str(info/'engine-id.json'),'.')]
binaries=[]
hiddenimports=['backend_'+engine]
if engine=='hydro':
    for package in ('pygimli','pgcore'):
        d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
    datas,binaries=collect_delvewheel_libs_directory('pgcore',datas=datas,binaries=binaries)
    datas+=collect_data_files('PyHydroGeophysX')
    hiddenimports+=['PyHydroGeophysX.inversion.ert_inversion']
    for dist in ('pygimli','pgcore','PyHydroGeophysX'):datas+=copy_metadata(dist)
else:
    for package in ('discretize','geoana'):
        d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
        datas,binaries=collect_delvewheel_libs_directory(package,datas=datas,binaries=binaries)
    datas+=collect_data_files('simpeg')
    datas+=copy_metadata('simpeg')
    hiddenimports+=['simpeg.electromagnetics.static.resistivity']
excluded=['PySide6','PyQt5','PyQt6','IPython','jupyterlab']
if engine=='hydro': excluded += ['simpeg','SimPEG','discretize','geoana','pymatsolver']
a=Analysis([str(root/'engine_worker.py')],pathex=[str(root)],binaries=binaries,datas=datas,
           hiddenimports=hiddenimports,excludes=excluded,noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ERTEngine',console=False,upx=False)
coll=COLLECT(exe,a.binaries,a.datas,name='ERTEngine',upx=False)
