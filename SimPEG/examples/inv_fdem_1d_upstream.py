# SimPEG functionality
import simpeg.electromagnetics.frequency_domain as fdem
from simpeg.utils import plot_1d_layer_model, download, mkvc
from simpeg import (
    maps,
    data,
    data_misfit,
    regularization,
    optimization,
    inverse_problem,
    inversion,
    directives,
)

# discretize functionality
from discretize import TensorMesh

# Basic Python functionality
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import tarfile

mpl.rcParams.update({"font.size": 14})

# URL to assets
data_source = "https://github.com/simpeg/user-tutorials/raw/main/assets/07-fdem/inv_fdem_1d_files.tar.gz"

# download the data
downloaded_data = download(data_source, overwrite=True)

# unzip the tarfile
tar = tarfile.open(downloaded_data, "r")
tar.extractall()
tar.close()

# path to the directory containing our data
dir_path = downloaded_data.split(".")[0] + os.path.sep

# files to work with
data_filename = dir_path + "em1dfm_data.txt"

# Load data
dobs = np.loadtxt(str(data_filename), skiprows=1)

# Extract frequency and observed data columns
frequencies = dobs[:, 0]
dobs = mkvc(dobs[:, 1:].T)

# Plot data
fig, ax = plt.subplots(1, 1, figsize=(5, 5))
ax.loglog(frequencies, np.abs(dobs[0::2]), "k-o", lw=2)
ax.loglog(frequencies, np.abs(dobs[1::2]), "k:o", lw=2)
ax.grid(which="both")
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("|Hs/Hp| (ppm)")
ax.set_title("Sounding Data")
ax.legend(["Real", "Imaginary"])
plt.show()

source_location = np.array([0.0, 0.0, 30.0])
source_orientation = "z"
moment = 1.0

receiver_location = np.array([10.0, 0.0, 30.0])
receiver_orientation = "z"
data_type = "ppm"

# Receiver list
receiver_list = []
receiver_list.append(
    fdem.receivers.PointMagneticFieldSecondary(
        receiver_location,
        orientation=receiver_orientation,
        data_type=data_type,
        component="real",
    )
)
receiver_list.append(
    fdem.receivers.PointMagneticFieldSecondary(
        receiver_location,
        orientation=receiver_orientation,
        data_type=data_type,
        component="imag",
    )
)

# Define source list
source_list = []
for freq in frequencies:
    source_list.append(
        fdem.sources.MagDipole(
            receiver_list=receiver_list,
            frequency=freq,
            location=source_location,
            orientation=source_orientation,
            moment=moment,
        )
    )

# Survey
survey = fdem.survey.Survey(source_list)

# 5% of the absolute value
uncertainties = 0.05 * np.abs(dobs) * np.ones(np.shape(dobs))

data_object = data.Data(survey, dobs=dobs, noise_floor=uncertainties)

# estimated host conductivity (S/m)
estimated_conductivity = 0.1

# minimum skin depth
d_min = 500.0 / np.sqrt(estimated_conductivity * frequencies.max())
print("MINIMUM SKIN DEPTH: {} m".format(d_min))

# maximum skin depth
d_max = 500.0 / np.sqrt(estimated_conductivity * frequencies.min())
print("MAXIMUM SKIN DEPTH: {} m".format(d_max))

depth_min = 0.5  # top layer thickness
depth_max = 200.0  # depth to lowest layer
geometric_factor = 1.1  # rate of thickness increase

# Increase subsequent layer thicknesses by the geometric factors until
# it reaches the maximum layer depth.
layer_thicknesses = [depth_min]
while np.sum(layer_thicknesses) < depth_max:
    layer_thicknesses.append(geometric_factor * layer_thicknesses[-1])

n_layers = len(layer_thicknesses) + 1  # Number of layers

log_conductivity_map = maps.ExpMap(nP=n_layers)

# Starting model is log-conductivity values (S/m)
starting_conductivity_model = np.log(1e-1 * np.ones(n_layers))

# Reference model is also log-resistivity values (S/m)
reference_conductivity_model = starting_conductivity_model.copy()

simulation_L2 = fdem.Simulation1DLayered(
    survey=survey, thicknesses=layer_thicknesses, sigmaMap=log_conductivity_map
)

dmis_L2 = data_misfit.L2DataMisfit(simulation=simulation_L2, data=data_object)

# Define 1D cell widths
h = np.r_[layer_thicknesses, layer_thicknesses[-1]]
h = np.flipud(h)

# Create regularization mesh
regularization_mesh = TensorMesh([h], "N")
print(regularization_mesh)

reg_L2 = regularization.WeightedLeastSquares(
    regularization_mesh,
    length_scale_x=10.0,
    reference_model=reference_conductivity_model,
    reference_model_in_smooth=False,
)

opt_L2 = optimization.InexactGaussNewton(
    maxIter=100, maxIterLS=20, cg_maxiter=20, cg_rtol=1e-3
)

inv_prob_L2 = inverse_problem.BaseInvProblem(dmis_L2, reg_L2, opt_L2)

update_jacobi = directives.UpdatePreconditioner(update_every_iteration=True)
starting_beta = directives.BetaEstimate_ByEig(beta0_ratio=5)
beta_schedule = directives.BetaSchedule(coolingFactor=2.0, coolingRate=3)
target_misfit = directives.TargetMisfit(chifact=1.0)

directives_list_L2 = [update_jacobi, starting_beta, beta_schedule, target_misfit]

# Here we combine the inverse problem and the set of directives
inv_L2 = inversion.BaseInversion(inv_prob_L2, directives_list_L2)

# Run the inversion
recovered_model_L2 = inv_L2.run(starting_conductivity_model)

dpred_L2 = simulation_L2.dpred(recovered_model_L2)

fig = plt.figure(figsize=(10, 5))
ax = [fig.add_axes([0.1 + ii * 0.5, 0.1, 0.37, 0.85]) for ii in range(2)]
for ii in range(2):
    ax[ii].loglog(frequencies, np.abs(dobs[ii::2]), "k-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_L2[ii::2]), "b-o", lw=2)
    ax[ii].grid(which="both")
    ax[ii].set_xlabel("Frequency (Hz)")
    ax[ii].set_ylabel("|Hs/Hp| (ppm)")
    ax[ii].legend(["Observed", "L2 Inversion"])
    if ii == 1:
        ax[ii].set_ylabel("")

ax[0].set_title("Real Component")
ax[1].set_title("Imaginary Component")
plt.show()

# true conductivities and layer thicknesses
true_conductivities = np.array([0.1, 1.0, 0.1])
true_layers = np.r_[20.0, 40.0, 160.0]

# Plot true model and recovered model
fig = plt.figure(figsize=(6, 6))

ax1 = fig.add_axes([0.2, 0.15, 0.7, 0.7])
plot_1d_layer_model(true_layers, true_conductivities, ax=ax1, color="k")
plot_1d_layer_model(
    layer_thicknesses, log_conductivity_map * recovered_model_L2, ax=ax1, color="b"
)
ax1.grid()
ax1.set_xlabel(r"Resistivity ($\Omega m$)")
x_min, x_max = true_conductivities.min(), true_conductivities.max()
ax1.set_xlim(0.9 * x_min, 1.5 * x_max)
ax1.legend(["True Model", "L2-Model"])
plt.show()

simulation_irls = fdem.simulation_1d.Simulation1DLayered(
    survey=survey,
    sigmaMap=log_conductivity_map,
    thicknesses=layer_thicknesses,
)

dmis_irls = data_misfit.L2DataMisfit(simulation=simulation_irls, data=data_object)

reg_irls = regularization.Sparse(
    regularization_mesh,
    alpha_s=0.01,
    alpha_x=1,
    reference_model_in_smooth=False,
    norms=[1.0, 1.0],
)

opt_irls = optimization.InexactGaussNewton(
    maxIter=100, maxIterLS=20, cg_maxiter=30, cg_rtol=1e-3
)

inv_prob_irls = inverse_problem.BaseInvProblem(dmis_irls, reg_irls, opt_irls)

starting_beta_irls = directives.BetaEstimate_ByEig(beta0_ratio=5)
update_jacobi_irls = directives.UpdatePreconditioner(update_every_iteration=True)
update_irls = directives.UpdateIRLS(
    cooling_factor=2,
    cooling_rate=3,
    f_min_change=1e-4,
    max_irls_iterations=30,
    chifact_start=1.0,
)

directives_list_irls = [update_irls, starting_beta_irls, update_jacobi_irls]

# Here we combine the inverse problem and the set of directives
inv_irls = inversion.BaseInversion(inv_prob_irls, directives_list_irls)

# Run the inversion
recovered_model_irls = inv_irls.run(starting_conductivity_model)

dpred_irls = simulation_irls.dpred(recovered_model_irls)

fig = plt.figure(figsize=(10, 5))
ax = [fig.add_axes([0.1 + ii * 0.5, 0.1, 0.37, 0.85]) for ii in range(2)]
for ii in range(2):
    ax[ii].loglog(frequencies, np.abs(dobs[ii::2]), "k-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_L2[ii::2]), "b-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_irls[ii::2]), "r-o", lw=2)
    ax[ii].grid(which="both")
    ax[ii].set_xlabel("Frequency (Hz)")
    ax[ii].set_ylabel("|Hs/Hp| (ppm)")
    ax[ii].legend(["True Sounding", "Predicted (L2-model)", "Predicted (IRLS)"])
    if ii == 1:
        ax[ii].set_ylabel("")

ax[0].set_title("Real Component")
ax[1].set_title("Imaginary Component")
plt.show()

# Plot true model and recovered model
fig = plt.figure(figsize=(6, 6))

ax1 = fig.add_axes([0.2, 0.15, 0.7, 0.7])
plot_1d_layer_model(true_layers, true_conductivities, ax=ax1, color="k")
plot_1d_layer_model(
    layer_thicknesses, log_conductivity_map * recovered_model_L2, ax=ax1, color="b"
)
plot_1d_layer_model(
    layer_thicknesses, log_conductivity_map * recovered_model_irls, ax=ax1, color="r"
)
ax1.grid()
ax1.set_xlabel(r"Conductivity ($S/m$)")
x_min, x_max = true_conductivities.min(), true_conductivities.max()
ax1.set_xlim(0.8 * x_min, 2 * x_max)
ax1.legend(["True Model", "L2 Model", "IRLS Model"])
plt.show()

# Wire maps to extract log-thicknesses and log-conductivities
wire_map = maps.Wires(("log_thicknesses", 2), ("log_resistivity", 3))

# Maping for layer thicknesses
log_thicknesses_map = maps.ExpMap() * wire_map.log_thicknesses

# Mapping for conductivities
log_resistivity_map = maps.ExpMap() * wire_map.log_resistivity

starting_parametric_model = np.log(np.r_[30.0, 20.0, 20, 0.5, 5])

reference_parametric_model = starting_parametric_model.copy()

simulation_parametric = fdem.simulation_1d.Simulation1DLayered(
    survey=survey,
    rhoMap=log_resistivity_map,
    thicknessesMap=log_thicknesses_map,
)

dmis_parametric = data_misfit.L2DataMisfit(
    simulation=simulation_parametric, data=data_object
)

reg_1 = regularization.Smallness(
    TensorMesh([(np.ones(2))], "0"),
    mapping=wire_map.log_thicknesses,
    reference_model=reference_parametric_model,
)

reg_2 = regularization.Smallness(
    TensorMesh([(np.ones(3))], "0"),
    mapping=wire_map.log_resistivity,
    reference_model=reference_parametric_model,
)

reg_parametric = reg_1 + reg_2
reg_parametric.multipliers = [1.0, 0.1]

opt_parametric = optimization.InexactGaussNewton(
    maxIter=100, maxIterLS=20, cg_maxiter=20, cg_rtol=1e-3
)

inv_prob_parametric = inverse_problem.BaseInvProblem(
    dmis_parametric, reg_parametric, opt_parametric
)

update_jacobi = directives.UpdatePreconditioner(update_every_iteration=True)
starting_beta = directives.BetaEstimate_ByEig(beta0_ratio=5)
beta_schedule = directives.BetaSchedule(coolingFactor=2.0, coolingRate=3)
target_misfit = directives.TargetMisfit(chifact=1.0)

directives_list_parametric = [
    update_jacobi,
    starting_beta,
    beta_schedule,
    target_misfit,
]

inv_parametric = inversion.BaseInversion(
    inv_prob_parametric, directives_list_parametric
)
recovered_model_parametric = inv_parametric.run(starting_parametric_model)

dpred_parametric = simulation_parametric.dpred(recovered_model_parametric)

fig = plt.figure(figsize=(10, 5))
ax = [fig.add_axes([0.1 + ii * 0.5, 0.1, 0.37, 0.85]) for ii in range(2)]
for ii in range(2):
    ax[ii].loglog(frequencies, np.abs(dobs[ii::2]), "k-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_L2[ii::2]), "b-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_irls[ii::2]), "r-o", lw=2)
    ax[ii].loglog(frequencies, np.abs(dpred_parametric[ii::2]), "g-o", lw=2)
    ax[ii].grid(which="both")
    ax[ii].set_xlabel("Frequency (Hz)")
    ax[ii].set_ylabel("|Hs/Hp| (ppm)")
    ax[ii].legend(
        [
            "True Sounding",
            "Predicted (L2-model)",
            "Predicted (IRLS)",
            "Predicted (Parametric)",
        ]
    )
    if ii == 1:
        ax[ii].set_ylabel("")

ax[0].set_title("Real Component")
ax[1].set_title("Imaginary Component")
plt.show()

fig = plt.figure(figsize=(6, 6))

ax1 = fig.add_axes([0.2, 0.15, 0.7, 0.7])
plot_1d_layer_model(true_layers, true_conductivities, ax=ax1, color="k")
plot_1d_layer_model(
    layer_thicknesses, log_conductivity_map * recovered_model_L2, ax=ax1, color="b"
)
plot_1d_layer_model(
    layer_thicknesses, log_conductivity_map * recovered_model_irls, ax=ax1, color="r"
)
plot_1d_layer_model(
    log_thicknesses_map * recovered_model_parametric,
    1 / (log_resistivity_map * recovered_model_parametric),
    ax=ax1,
    color="g",
)
ax1.grid()
ax1.set_xlabel(r"Resistivity ($\Omega m$)")
x_min, x_max = true_conductivities.min(), true_conductivities.max()
ax1.set_xlim(0.9 * x_min, 2 * x_max)
ax1.set_ylim([np.sum(layer_thicknesses), 0])
ax1.legend(["True Model", "L2 Model", "IRLS Model", "Parametric Model"])
plt.show()