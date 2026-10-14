#!/usr/bin/env python3
"""Synthetic instrument-style demonstrations; not calibrated commercial instruments.

FDEM uses 30 kHz, 0.32/0.71/1.18 m coil separations (as in SimPEG's
official loop-loop example), in two coplanar orientations. TDEM uses
a circular airborne loop, finite trapezoidal waveform, and dB/dt gates.
Layer boundaries are fixed in both examples; only conductivity is inverted.
"""
import argparse
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import matplotlib.pyplot as plt
from discretize import TensorMesh
from simpeg import (maps, regularization, data_misfit, optimization,
                    inverse_problem, inversion, directives)
from simpeg.electromagnetics import frequency_domain as fdem, time_domain as tdem
from simpeg.utils import plot_1d_layer_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=["fdem", "tdem"])
    method = parser.parse_args().method
    output = ROOT / "results" / f"{method}_instrument_style"
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    sigma_map = maps.ExpMap(nP=3)
    if method == "fdem":
        thicknesses = np.r_[0.4, 1.2]
        truth = np.r_[0.01, 0.04, 0.015]
        sources, labels = [], []
        for orientation in ["z", "x"]:
            for offset in [0.32, 0.71, 1.18]:
                rx_location = np.r_[offset, 0.0, 0.25]
                receivers = [fdem.receivers.PointMagneticFieldSecondary(
                    rx_location, orientation=orientation, component=component,
                    data_type="ppm") for component in ["real", "imag"]]
                sources.append(fdem.sources.MagDipole(receivers, frequency=30000,
                    location=np.r_[0.0, 0.0, 0.25], orientation=orientation))
                labels.extend([f"{orientation}, {offset} m, {c}" for c in ["real", "imag"]])
        survey = fdem.Survey(sources)
        simulation = fdem.Simulation1DLayered(survey=survey, thicknesses=thicknesses,
                                             sigmaMap=sigma_map)
        floor, units = 0.1, "Secondary / primary field (ppm)"
        settings = {"frequency_hz": 30000, "coil_separations_m": [0.32, 0.71, 1.18],
                    "height_m": 0.25, "dipole_orientations": ["z", "x"],
                    "data_order": labels}
    else:
        thicknesses = np.r_[20.0, 40.0]
        truth = np.r_[0.01, 0.1, 0.01]
        times = np.logspace(-5, -2, 31)
        location = np.r_[0.0, 0.0, 30.0]
        waveform = tdem.sources.TrapezoidWaveform(ramp_on=[-0.002, -0.001],
                                                 ramp_off=[-0.00002, 0.0])
        receiver = tdem.receivers.PointMagneticFluxTimeDerivative(location, times,
                                                                orientation="z")
        source = tdem.sources.CircularLoop([receiver], location=location,
                     radius=10.0, current=1.0, waveform=waveform, orientation="z")
        survey = tdem.Survey([source])
        simulation = tdem.Simulation1DLayered(survey=survey, thicknesses=thicknesses,
                                             sigmaMap=sigma_map)
        floor, units = 1e-13, "|dBz/dt| (T/s)"
        settings = {"height_m": 30, "loop_radius_m": 10, "current_a": 1,
                    "ramp_on_s": [-0.002, -0.001], "ramp_off_s": [-0.00002, 0],
                    "gate_center_times_s": times.tolist()}
    true_model = np.log(truth)
    starting = np.full(3, np.log(0.02))
    observations = simulation.make_synthetic_data(true_model, relative_error=0.03,
                              noise_floor=floor, add_noise=True, random_seed=42)
    initial = simulation.dpred(starting).copy()
    mesh = TensorMesh([np.r_[thicknesses, thicknesses[-1]]])
    reg = regularization.WeightedLeastSquares(mesh, alpha_s=1, alpha_x=0,
                                              reference_model=starting)
    misfit = data_misfit.L2DataMisfit(simulation=simulation, data=observations)
    opt = optimization.ProjectedGNCG(maxIter=50, maxIterLS=20, cg_maxiter=20,
                 cg_rtol=1e-5, lower=np.log(1e-4), upper=np.log(2.0))
    problem = inverse_problem.BaseInvProblem(misfit, reg, opt)
    inv = inversion.BaseInversion(problem, [directives.BetaEstimate_ByEig(
           beta0_ratio=0.01, random_seed=42), directives.BetaSchedule(
           coolingFactor=2, coolingRate=2), directives.TargetMisfit()])
    recovered = inv.run(starting)
    predicted = simulation.dpred(recovered)
    std = observations.standard_deviation
    initial_rms = float(np.sqrt(np.mean(((initial-observations.dobs)/std)**2)))
    final_rms = float(np.sqrt(np.mean(((predicted-observations.dobs)/std)**2)))
    assert np.all(np.isfinite(predicted)) and np.all(np.isfinite(recovered))
    assert final_rms < initial_rms and final_rms < 1.5
    np.savez_compressed(output / "inversion.npz", starting_model=starting,
          true_model=true_model, recovered_model=recovered, observed=observations.dobs,
          predicted=predicted, standard_deviation=std, layer_thicknesses=thicknesses)
    np.savetxt(output / "data_fit.csv", np.c_[observations.dobs, predicted, std],
          delimiter=",", header="observed,predicted,standard_deviation", comments="")
    np.savetxt(output / "conductivity_model.csv", np.c_[truth, np.exp(starting), np.exp(recovered)],
          delimiter=",", header="true_S_per_m,starting_S_per_m,recovered_S_per_m", comments="")
    report = {"method": method, "status": "passed", "n_data": int(survey.nD),
              "n_parameters": 3, "random_seed": 42, "fixed_layer_thicknesses_m": thicknesses.tolist(),
              "initial_weighted_rms": initial_rms, "final_weighted_rms": final_rms,
              "iterations": int(opt.iter), "elapsed_seconds": round(time.monotonic()-start, 3),
              "settings": settings,
              "limitation": "Synthetic illustrative geometry, fixed layer boundaries; not a calibrated instrument or real survey inversion."}
    (output / "summary.json").write_text(json.dumps(report, indent=2)+"\n")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    plot_1d_layer_model(thicknesses, truth, ax=axes[0], color="k", label="True")
    plot_1d_layer_model(thicknesses, np.exp(recovered), ax=axes[0], color="C1", label="Recovered")
    axes[0].set_xlabel("Conductivity (S/m)")
    axes[0].set_ylabel("Depth (m)")
    axes[0].legend()
    if method == "fdem":
        axes[1].errorbar(np.arange(survey.nD), observations.dobs, yerr=std, fmt="ko", label="Observed")
        axes[1].plot(predicted, "C1x", label="Predicted")
        axes[1].set_xlabel("Channel index (see summary.json for ordering)")
    else:
        axes[1].loglog(times, np.abs(observations.dobs), "ko", label="Observed")
        axes[1].loglog(times, np.abs(predicted), "C1-", label="Predicted")
        axes[1].set_xlabel("Time after turn-off (s)")
    axes[1].set_ylabel(units)
    axes[1].legend()
    axes[1].grid(True, which="both", alpha=0.3)
    fig.suptitle(f"Synthetic {method.upper()} instrument-style inversion (fixed layer boundaries)")
    fig.tight_layout()
    fig.savefig(output / "model_and_fit.png", dpi=150)
    plt.close(fig)
    print("VALIDATION", json.dumps(report))


if __name__ == "__main__":
    main()
