"""Exercise an optional executable against known positive resistivity data."""
import json,os,shutil,subprocess,sys,math,csv
from pathlib import Path
engine,exe,folder=sys.argv[1],Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve()
folder.mkdir(parents=True,exist_ok=True)
source=Path(__file__).resolve().parents[1]/'examples'/'homogeneous.csv'
shutil.copy2(source,folder/'survey.csv')
settings=dict(start_resistivity=80,max_iterations=5,mesh_depth=4,max_cell_area=.5)
(folder/'settings.json').write_text(json.dumps(settings))
process=subprocess.run([str(exe),'--worker',str(folder)],cwd=folder,timeout=180)
if process.returncode:
    raise RuntimeError((folder/'solver.log').read_text(encoding='utf-8',errors='replace'))
result=json.loads((folder/'run.json').read_text())
assert result['backend']==engine and result['measurements']==35
assert math.isfinite(result['relative_rms_percent']) and result['relative_rms_percent']<8
assert (folder/'model.png').stat().st_size>10000
with (folder/'observed_predicted.csv').open() as stream:
    assert all(float(row['predicted_ohm_m'])>0 for row in csv.DictReader(stream))
print(json.dumps(result,indent=2))
