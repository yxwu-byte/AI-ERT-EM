"""Rebuild deterministic synthetic samples and equivalent interchange examples."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime import configure_runtime
configure_runtime()
import csv
import json
import numpy as np
from pygimli.physics import ert
from survey_io import write_csv,geometric_factor

folder=Path(__file__).resolve().parents[1]/'examples'
entries=[dict(id='homogeneous',label='Homogeneous half-space • Wenner',description='100 ohm m reference; 16 electrodes, 35 observations.'),
         dict(id='conductive_block',label='Conductive target • Wenner',description='Synthetic 30 ohm m shallow block within 100 ohm m background.'),
         dict(id='resistive_block',label='Resistive target • dipole–dipole',description='Synthetic 300 ohm m target within 100 ohm m background.'),
         dict(id='layered',label='Two layers • Wenner',description='60 ohm m upper layer over 180 ohm m lower layer.')]
for item in entries:
    scheme=ert.createData(elecs=np.arange(16,dtype=float),schemeName='dd' if item['id']=='resistive_block' else 'wa')
    mesh=ert.createInversionMesh(scheme,paraDepth=5,paraMaxCellSize=.5)
    centers=np.asarray(mesh.cellCenters()); model=np.full(mesh.cellCount(),100.)
    if item['id'] in ('conductive_block','resistive_block'):
        model[(centers[:,0]>5)&(centers[:,0]<10)&(centers[:,1]>-3)&(centers[:,1]<-.5)]=30 if item['id']=='conductive_block' else 300
    if item['id']=='layered': model=np.where(centers[:,1]>-2,60.,180.)
    data=ert.simulate(mesh,scheme=scheme,res=model,noiseLevel=0,verbose=False)
    data['err']=np.full(data.size(),.03)
    rows=[]
    for i in range(data.size()):
        coords=[float(data.sensorPosition(int(data[key][i])).x()) for key in ('a','b','m','n')]
        rows.append(dict(zip(('ax','bx','mx','nx','rhoa','error'),[*coords,float(data['rhoa'][i]),.03])))
    write_csv(folder/(item['id']+'.csv'),rows)
    # Use an ASCII current directory for the native exporter on Windows too.
    from contextlib import chdir
    with chdir(folder): data.save(item['id']+'.ohm')
    item['file']=item['id']+'.csv';item['measurements']=len(rows);item['synthetic']=True
    if item['id']=='conductive_block':
        with (folder/'resistance_percent.tsv').open('w',newline='') as stream:
            writer=csv.writer(stream,delimiter='\t');writer.writerow(['A_x','B_x','M_x','N_x','resistance','error_pct'])
            for row in rows:
                coords=[row[k] for k in ('ax','bx','mx','nx')]
                writer.writerow([*coords,row['rhoa']/geometric_factor(*coords),3])
        with (folder/'voltage_current.csv').open('w',newline='') as stream:
            writer=csv.writer(stream,delimiter=';');writer.writerow(['ax','bx','mx','nx','voltage','current_ma','error_pct'])
            for row in rows:
                coords=[row[k] for k in ('ax','bx','mx','nx')]
                writer.writerow([*coords,row['rhoa']/geometric_factor(*coords)*100,100,3]) # mV at 100 mA
        with (folder/'electrode_ids.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['a','b','m','n','rhoa','err'])
            for row in rows: writer.writerow([*(int(row[k])+1 for k in ('ax','bx','mx','nx')),row['rhoa'],.03])
        with (folder/'electrodes.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['id','x']);writer.writerows((i+1,i) for i in range(16))
        lines=['Synthetic conductive block', '1', '1', str(len(rows)), '1', '0']
        for row in rows:
            lines.append(f"{(row['ax']+row['bx'])/2:.12g} {row['mx']-row['ax']:.12g} {row['rhoa']:.15g}")
        (folder/'wenner_res2dinv.dat').write_text('\n'.join(lines+['0','0','0'])+'\n')
(folder/'catalog.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
print('Generated',len(entries),'synthetic surveys and conversion examples.')
