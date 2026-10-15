"""Verify the bundled ERT inversion with a small synthetic conductive anomaly."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path

# Set these before importing numerical libraries. The pyGIMLi Jacobian needs
# one BERT thread on the tested Linux worker.
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "BERT_NUM_THREADS"):
    os.environ[name] = "1"
os.environ.setdefault("MPLBACKEND", "Agg")
cache = Path(__file__).parent.resolve() / ".cache"
cache.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(cache))
os.environ.setdefault("XDG_CONFIG_HOME", str(cache / "config"))

import matplotlib.pyplot as plt
import numpy as np
import pygimli as pg
from pygimli.physics import ert
import PyHydroGeophysX
from PyHydroGeophysX.inversion.ert_inversion import ERTInversion


def chi2(predicted, observed, errors):
    return float(np.mean(((np.log(predicted) - np.log(observed)) / np.log1p(errors)) ** 2))


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    package_path = Path(PyHydroGeophysX.__file__).resolve()
    expected = Path(__file__).parent.resolve() / "source/PyHydroGeophysX"
    if not package_path.is_relative_to(expected):
        raise RuntimeError(f"Expected the editable bundled source, imported {package_path}")

    survey = ert.createData(elecs=np.arange(12, dtype=float), schemeName="wa")
    forward_mesh = ert.createInversionMesh(survey, paraDepth=3, paraMaxCellSize=1)
    centers = np.asarray(forward_mesh.cellCenters())
    true_model = np.where((centers[:, 0] > 4) & (centers[:, 0] < 7) &
                          (centers[:, 1] > -2), 40.0, 100.0)
    data = ert.simulate(forward_mesh, scheme=survey, res=true_model,
                        noiseLevel=0, verbose=False)
    # Assigned uncertainties include values below the upstream 1% default floor.
    data["err"] = np.linspace(0.005, 0.03, data.size())
    source = output / "synthetic.ohm"
    data.save(str(source))
    # Read the saved values: this is exactly the input the inversion will load.
    data = ert.load(str(source))
    observed, errors = np.asarray(data["rhoa"]), np.asarray(data["err"])
    mesh = ert.ERTManager(data).createMesh(data=data, paraDepth=3, paraMaxCellSize=1)
    settings = dict(lambda_val=20, max_iterations=8, method="cgls",
                    model_constraints=[1.0, 100000.0], lambda_rate=1.0,
                    min_relative_error=float(errors.min()),
                    max_relative_error=float(errors.max()),
                    use_gpu=False, parallel=False, n_jobs=1)
    engine = ERTInversion(data_file=str(source), mesh=mesh, **settings)
    engine.setup()
    starting_model = pg.Vector(engine.fwd_operator.paraDomain.cellCount(), float(np.median(observed)))
    initial_chi2 = chi2(np.asarray(engine.fwd_operator.response(starting_model)), observed, errors)
    result = engine.run()
    model, predicted = np.asarray(result.final_model), np.asarray(result.predicted_data)
    final_chi2 = chi2(predicted, observed, errors)
    jacobian = np.asarray(engine.fwd_operator.jacobian())
    if (model.shape != (result.mesh.cellCount(),) or predicted.shape != observed.shape or
            not np.isfinite(model).all() or not np.isfinite(predicted).all() or
            not np.all((model >= 1.0) & (model <= 100000.0)) or not np.all(predicted > 0) or
            not np.isfinite(jacobian).all() or not np.any(jacobian != 0) or
            not np.isfinite(final_chi2) or final_chi2 >= initial_chi2):
        raise RuntimeError("ERT output failed shape, bounds, sensitivity, or fit-improvement checks")
    np.testing.assert_allclose(np.diag(engine.Wdert), 1 / np.log1p(errors))

    centers = np.asarray(result.mesh.cellCenters())
    np.savetxt(output / "model.csv", np.c_[centers[:, :2], model], delimiter=",",
               header="x_m,z_m,resistivity_ohm_m", comments="")
    np.savetxt(output / "data_fit.csv", np.c_[observed, predicted, errors], delimiter=",",
               header="observed_rhoa,predicted_rhoa,relative_error", comments="")
    result.mesh["resistivity_ohm_m"] = pg.Vector(model)
    result.mesh.exportVTK(str(output / "model"))
    fig, ax = plt.subplots(figsize=(9, 3))
    pg.show(result.mesh, model, ax=ax, logScale=True, label="Resistivity (ohm m)")
    fig.savefig(output / "inversion.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    summary = {
        "pyhydrogeophysx_version": version("PyHydroGeophysX"),
        "pygimli_version": version("pygimli"),
        "source": "source/PyHydroGeophysX", "survey": "synthetic Wenner, no added noise",
        "n_data": int(data.size()), "n_parameters": int(model.size),
        "initial_chi2": initial_chi2, "final_chi2": final_chi2,
        "chi2_definition": "mean(((log(predicted)-log(observed))/log1p(relative_error))**2)",
        "relative_rms_percent": float(100 * np.sqrt(np.mean(((predicted - observed) / observed)**2))),
        "chi2_history": [float(v) for v in result.iteration_chi2],
        "settings": settings,
        "checks": "local source import, finite output, model bounds, nonzero Jacobian, preserved errors, improved fit",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results/ert")
    run(parser.parse_args().output.resolve())
