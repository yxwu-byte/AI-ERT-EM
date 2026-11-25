"""Adapter for the bundled upstream PyHydroGeophysX ERT solver."""
from pathlib import Path
from contextlib import chdir
from core import load_csv
from backend_common import finish_run


def run(input_path, output_path, settings):
    settings.validate()
    rows=load_csv(input_path)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import pygimli as pg
    from pygimli.physics import ert
    import PyHydroGeophysX
    from PyHydroGeophysX.inversion.ert_inversion import ERTInversion
    output=Path(output_path).resolve(); output.mkdir(parents=True,exist_ok=True)
    data=pg.DataContainerERT()
    positions=sorted({row[key] for row in rows for key in ('ax','bx','mx','nx')})
    indices={x:data.createSensor([x,0,0]) for x in positions}
    for i,row in enumerate(rows):
        data.createFourPointData(i,*(indices[row[key]] for key in ('ax','bx','mx','nx')))
    data['rhoa']=[row['rhoa'] for row in rows]
    errors=np.array([max(row['error'],settings.error_floor) for row in rows])
    data['err']=errors
    data['k']=ert.createGeometricFactors(data)
    data['r']=np.asarray(data['rhoa'])/np.asarray(data['k'])
    mesh_options={}
    if settings.mesh_depth: mesh_options['paraDepth']=settings.mesh_depth
    if settings.max_cell_area: mesh_options['paraMaxCellSize']=settings.max_cell_area
    mesh=ert.ERTManager(data).createMesh(data=data,**mesh_options)
    bounds=[settings.lower_resistivity or 1e-6,settings.upper_resistivity or 1e10]
    options=dict(lambda_val=settings.regularization,max_iterations=settings.max_iterations,
                 method=settings.hydro_solver,model_constraints=bounds,lambda_rate=np.sqrt(settings.lambda_factor),
                 min_relative_error=float(errors.min()),max_relative_error=float(errors.max()),
                 use_gpu=False,parallel=False,n_jobs=1)
    with chdir(output):
        data.save('survey.ohm')
        engine=ERTInversion(data_file='survey.ohm',mesh=mesh,**options)
        engine.setup()
        result=engine.run(initial_model=np.full(engine.fwd_operator.paraDomain.cellCount(),settings.start_resistivity))
        result.mesh['Resistivity']=pg.Vector(np.asarray(result.final_model).ravel())
        result.mesh.exportVTK('model')
    fig,ax=plt.subplots(figsize=(10,4))
    pg.show(result.mesh,np.asarray(result.final_model).ravel(),ax=ax,logScale=True,label='Resistivity (ohm m)')
    fig.savefig(output/'model.png',dpi=150,bbox_inches='tight'); plt.close(fig)
    centers=np.asarray(result.mesh.cellCenters())
    np.savetxt(output/'model.csv',np.c_[centers[:,:2],np.asarray(result.final_model).ravel()],delimiter=',',
               header='x_m,z_m,resistivity_ohm_m',comments='')
    options['stop']='Upstream fixed chi-squared < 1.5 or < 1% change, or iteration limit'
    options['note']='Smooth-model solver using pyGIMLi forward modelling; pyGIMLi-specific controls do not apply.'
    return finish_run(output,rows,result.predicted_data,settings,'hydro',PyHydroGeophysX.__version__,options)
