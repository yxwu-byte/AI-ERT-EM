#!/usr/bin/env python3
"""Run official SimPEG notebooks as scripts, saving figures and inversion evidence."""
import argparse
import json
import os
from pathlib import Path
import sys
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=["ert", "tdem", "fdem"])
    args = parser.parse_args()
    folder, name = {
        "ert": ("05-dcr", "inv_dcr_2d"),
        "tdem": ("08-tdem", "inv_tdem_1d"),
        "fdem": ("07-fdem", "inv_fdem_1d"),
    }[args.method]
    output = ROOT / "results" / args.method
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(output)
    start = time.monotonic()
    notebook = ROOT / "user-tutorials" / "notebooks" / folder / f"{name}.ipynb"
    cells = json.loads(notebook.read_text())["cells"]
    source = "\n\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    upstream = ROOT / "examples" / f"{name}_upstream.py"
    upstream.write_text(source)
    # Use the identical archive from the pinned tutorial checkout, with safe extraction.
    archive = ROOT / "user-tutorials" / "assets" / folder / f"{name}_files.tar.gz"
    with tarfile.open(archive) as tar:
        tar.extractall(output, filter="data")
    first = source.index("# download the data")
    last = source.index("# files to work with", first)
    source = source[:first] + f'dir_path = {str(output / (name + "_files"))!r} + os.path.sep\n\n' + source[last:]
    # Make power-iteration estimates repeatable without changing inversion settings.
    source = source.replace("directives.BetaEstimate_ByEig(", "directives.BetaEstimate_ByEig(random_seed=42, ")
    # The upstream TDEM notebook plots conductivity but labels three axes as resistivity.
    if args.method == "tdem":
        source = source.replace('ax1.set_xlabel(r"Resistivity ($\\Omega m$)")',
                                'ax1.set_xlabel("Conductivity (S/m)")')
    runnable = ROOT / "examples" / f"{name}_local.py"
    runnable.write_text(source)

    import numpy as np
    import matplotlib.pyplot as plt
    import simpeg
    from simpeg import inversion

    np.random.seed(42)
    records = []
    fig_counter = 0

    def save_figures(*unused_args, **unused_kwargs):
        nonlocal fig_counter
        for number in plt.get_fignums():
            fig_counter += 1
            fig = plt.figure(number)
            fig.savefig(output / f"figure_{fig_counter:02d}.png", dpi=150, bbox_inches="tight")
            plt.close(fig)

    plt.show = save_figures
    original_run = inversion.BaseInversion.run

    def recorded_run(self, starting_model):
        problem = self.invProb
        misfit = problem.dmisfit.objfcts[0]
        simulation = misfit.simulation
        observations = misfit.data
        dobs = observations.dobs.copy()
        std = observations.standard_deviation.copy()
        assert np.all(np.isfinite(std)) and np.all(std > 0), "Invalid uncertainties"
        initial_prediction = simulation.dpred(starting_model).copy()
        inversion_start = time.monotonic()
        recovered = original_run(self, starting_model)
        predicted = simulation.dpred(recovered).copy()
        index = len(records) + 1
        wrms_initial = float(np.sqrt(np.mean(((initial_prediction - dobs) / std) ** 2)))
        wrms_final = float(np.sqrt(np.mean(((predicted - dobs) / std) ** 2)))
        record = {
            "inversion": index,
            "n_data": int(dobs.size),
            "n_parameters": int(recovered.size),
            "initial_weighted_rms": wrms_initial,
            "final_weighted_rms": wrms_final,
            "iterations": int(problem.opt.iter),
            "elapsed_seconds": round(time.monotonic() - inversion_start, 3),
            "finite_positive_model": bool(np.all(np.isfinite(np.exp(recovered))) and np.all(np.exp(recovered) > 0)),
            "fit_improved": bool(wrms_final < wrms_initial),
            "near_noise_level": bool(wrms_final <= 1.5),
        }
        arrays = dict(starting_model=starting_model, recovered_model=recovered,
                      observed=dobs, predicted=predicted, initial_predicted=initial_prediction,
                      standard_deviation=std)
        if hasattr(simulation, "thicknesses"):
            arrays["layer_thicknesses"] = simulation.thicknesses
        if hasattr(simulation, "mesh"):
            arrays["cell_centers"] = simulation.mesh.cell_centers
            simulation.mesh.save(str(output / f"mesh_{index}.json"))
        regularizer = problem.reg.objfcts[0]
        if hasattr(regularizer, "active_cells") and regularizer.active_cells is not None:
            arrays["active_cells"] = regularizer.active_cells
        np.savez_compressed(output / f"inversion_{index}.npz", **arrays)
        np.savetxt(output / f"data_fit_{index}.csv",
                   np.c_[dobs, predicted, std, (predicted - dobs) / std], delimiter=",",
                   header="observed,predicted,standard_deviation,normalized_residual", comments="")
        np.savetxt(output / f"model_{index}.csv", np.c_[starting_model, recovered], delimiter=",",
                   header="starting_log_parameter,recovered_log_parameter", comments="")
        records.append(record)
        (output / "inversions.json").write_text(json.dumps(records, indent=2) + "\n")
        print("\nVALIDATION", json.dumps(record), flush=True)
        assert record["finite_positive_model"] and np.all(np.isfinite(predicted)), "Nonfinite result"
        assert record["fit_improved"], "Inversion failed to improve the data fit"
        return recovered

    inversion.BaseInversion.run = recorded_run
    report = {"method": args.method, "simpeg_version": simpeg.__version__,
              "source_notebook": str(notebook.relative_to(ROOT)), "random_seed": 42}
    try:
        namespace = {"__name__": "__main__", "__file__": str(runnable)}
        exec(compile(source, str(runnable), "exec"), namespace)
        save_figures()
        report["status"] = "passed"
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        traceback.print_exc()
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - start, 3)
        report["inversions"] = records
        report["figures_saved"] = fig_counter
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
