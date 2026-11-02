"""Real 2.5D SimPEG DC inversion of the same four-electrode observations."""
from pathlib import Path
from core import load_csv
from survey_io import geometric_factor
from backend_common import finish_run


def run(input_path, output_path, settings):
    settings.validate()
    rows = load_csv(input_path)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import simpeg
    from discretize import TensorMesh
    from pymatsolver import SolverLU
    from simpeg import maps, data, data_misfit, regularization, optimization, inverse_problem, inversion, directives
    from simpeg.electromagnetics.static import resistivity as dc
    output = Path(output_path).resolve(); output.mkdir(parents=True,exist_ok=True)
    xs = np.unique([row[key] for row in rows for key in ('ax','bx','mx','nx')])
    span = float(xs[-1]-xs[0])
    h = np.sqrt(settings.max_cell_area) if settings.max_cell_area else float(np.min(np.diff(xs)))/2
    depth = settings.mesh_depth or span * 0.3
    nx, nz = max(4,int(np.ceil(span/h))), max(3,int(np.ceil(depth/h)))
    if (nx+12)*(nz+6) > 20000:
        raise ValueError('Requested SimPEG mesh exceeds 20,000 cells. Increase cell area or reduce depth.')
    mesh = TensorMesh([[(h,6,-1.4),(h,nx),(h,6,1.4)],[(h,6,-1.4),(h,nz)]])
    mesh.origin = [xs[0]-sum(mesh.h[0][:6]), -sum(mesh.h[1])]
    sources=[]
    for row in rows:
        receiver = dc.receivers.Dipole(np.array([[row['mx'],0.]]),np.array([[row['nx'],0.]]),data_type='volt')
        sources.append(dc.sources.Dipole([receiver],location_a=[row['ax'],0.],location_b=[row['bx'],0.]))
    survey=dc.Survey(sources)
    factors=np.array([geometric_factor(*(row[key] for key in ('ax','bx','mx','nx'))) for row in rows])
    observed=np.array([row['rhoa'] for row in rows])/factors
    errors=np.array([max(row['error'],settings.error_floor) for row in rows])
    dataset=data.Data(survey,dobs=observed,standard_deviation=np.abs(observed)*errors)
    simulation=dc.Simulation2DNodal(mesh,survey=survey,rhoMap=maps.ExpMap(mesh),solver=SolverLU,storeJ=True)
    misfit=data_misfit.L2DataMisfit(data=dataset,simulation=simulation)
    reg=regularization.WeightedLeastSquares(mesh,alpha_s=1e-4,alpha_x=1,alpha_y=1)
    start=np.full(mesh.nC,np.log(settings.start_resistivity))
    lower=np.log(settings.lower_resistivity) if settings.lower_resistivity else -np.inf
    upper=np.log(settings.upper_resistivity) if settings.upper_resistivity else np.inf
    opt=optimization.ProjectedGNCG(maxIter=settings.max_iterations,lower=lower,upper=upper,maxIterCG=30,tolCG=1e-4)
    problem=inverse_problem.BaseInvProblem(misfit,reg,opt,beta=settings.regularization)
    steps=[directives.BetaSchedule(coolingFactor=1/settings.lambda_factor,coolingRate=1),directives.TargetMisfit(chifact=1)]
    model=inversion.BaseInversion(problem,directiveList=steps).run(start)
    predicted=simulation.dpred(model)*factors
    rho=np.exp(model)
    fig,ax=plt.subplots(figsize=(10,4))
    from matplotlib.colors import LogNorm
    artist=mesh.plot_image(rho,ax=ax,pcolor_opts={'norm':LogNorm(),'cmap':'Spectral_r'})[0]
    fig.colorbar(artist,ax=ax,label='Resistivity (ohm m)')
    ax.set_xlim(xs[0],xs[-1]); ax.set_ylim(-depth,0); ax.set_xlabel('Distance (m)'); ax.set_ylabel('Elevation (m)')
    fig.savefig(output/'model.png',dpi=150,bbox_inches='tight'); plt.close(fig)
    np.savetxt(output/'model.csv',np.c_[mesh.cell_centers,rho],delimiter=',',header='x_m,z_m,resistivity_ohm_m',comments='')
    mesh.serialize()  # Ensure the mesh has a serializable native representation.
    mesh.save(str(output/'mesh.json'))
    options=dict(model='Smooth log-resistivity L2',solver='ProjectedGNCG / SciPy LU',beta=settings.regularization,
                 lambda_factor=settings.lambda_factor,cell_width_m=float(h),core_depth_m=depth,mesh_cells=mesh.nC,
                 lower_resistivity=settings.lower_resistivity,upper_resistivity=settings.upper_resistivity,
                 stop='Native voltage-data chi-squared target 1 or iteration/optimizer limit',
                 note='pyGIMLi-only robust, blocky, vertical smoothing and dPhi controls do not apply.')
    return finish_run(output,rows,predicted,settings,'simpeg',simpeg.__version__,options)
