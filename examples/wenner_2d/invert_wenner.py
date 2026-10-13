"""Convert the bundled RES2DINV Wenner survey and invert with pyGIMLi 1.6.1."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pygimli as pg
from pygimli.physics import ert


def convert(source, relative_error):
    lines = source.read_text().splitlines()
    if int(lines[2]) != 1 or int(lines[4]) != 1 or int(lines[5]) != 0:
        raise ValueError("Expected Wenner-alpha, midpoint positions, and no IP.")
    count = int(lines[3])
    rows = np.loadtxt(lines[6:6 + count])
    if rows.shape != (count, 3) or not np.isfinite(rows).all():
        raise ValueError("Invalid measurement rows.")
    midpoint, spacing, rhoa = rows.T
    if np.any(spacing <= 0) or np.any(rhoa <= 0):
        raise ValueError("Spacing and apparent resistivity must be positive.")
    # Spatial order is A, M, N, B for Wenner-alpha; API order is A, B, M, N.
    positions = np.column_stack((midpoint - 1.5 * spacing,
                                 midpoint + 1.5 * spacing,
                                 midpoint - 0.5 * spacing,
                                 midpoint + 0.5 * spacing))
    coordinates, inverse = np.unique(positions, return_inverse=True)
    indices = inverse.reshape(count, 4)
    survey = pg.DataContainerERT()
    for x in coordinates:
        survey.createSensor([float(x), 0, 0])
    for i, (a, b, m, n) in enumerate(indices):
        survey.createFourPointData(i, int(a), int(b), int(m), int(n))
    survey["rhoa"] = rhoa
    survey["k"] = ert.createGeometricFactors(survey, numerical=False)
    survey["err"] = np.full(count, relative_error)
    np.testing.assert_allclose(survey["k"], 2 * np.pi * spacing, rtol=1e-10)
    if survey.size() != count or survey.checkDataValidity() is False:
        raise ValueError("Converted survey is invalid.")
    return survey, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("res2dinv-wenner32.dat"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("inversion_results"))
    parser.add_argument("--relative-error", type=float, default=0.03)
    parser.add_argument("--lam", type=float, default=20.0)
    args = parser.parse_args()
    if not 0 < args.relative_error < 1 or args.lam <= 0:
        parser.error("Relative error must be in (0, 1), and lambda must be positive.")
    args.output.mkdir(parents=True, exist_ok=True)
    survey, rows = convert(args.input, args.relative_error)
    converted = args.output / "wenner32.ohm"
    survey.save(str(converted))
    reloaded = pg.DataContainerERT(str(converted))
    assert reloaded.size() == len(rows)
    for token in ("a", "b", "m", "n", "rhoa", "err"):
        np.testing.assert_allclose(reloaded[token], survey[token], rtol=1e-6)

    manager = ert.ERTManager(survey, verbose=True)
    model = np.asarray(manager.invert(lam=args.lam, paraDepth=25,
                                     paraMaxCellSize=4, quality=34,
                                     maxIter=15, verbose=True))
    response = np.asarray(manager.inv.response)
    if not np.isfinite(model).all() or np.any(model <= 0) or not np.isfinite(response).all():
        raise RuntimeError("Inversion produced invalid results.")
    domain = manager.paraDomain
    centers = np.asarray(domain.cellCenters())
    with (args.output / "model.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["cell", "x_m", "depth_m", "resistivity_ohm_m"])
        writer.writerows((i, float(c[0]), float(-c[1]), float(r))
                         for i, (c, r) in enumerate(zip(centers, model)))
    np.savetxt(args.output / "data_fit.csv", np.column_stack((rows, response,
               (response - rows[:, 2]) / rows[:, 2] * 100)), delimiter=",",
               header="midpoint_m,spacing_m,observed_rhoa_ohm_m,predicted_rhoa_ohm_m,residual_percent",
               comments="", fmt="%.8g")
    domain["resistivity_ohm_m"] = pg.Vector(model)
    domain.exportVTK(str(args.output / "model"))
    summary = dict(pygimli_version=pg.__version__, measurements=survey.size(),
                   electrodes=survey.sensorCount(), assumed_relative_error=args.relative_error,
                   lambda_initial=args.lam, parameter_depth_m=25, max_cell_area_m2=4,
                   model_cells=len(model), chi_squared=float(manager.inv.chi2()),
                   relative_rms_percent=float(manager.inv.relrms()),
                   resistivity_min_ohm_m=float(model.min()),
                   resistivity_max_ohm_m=float(model.max()),
                   chi_squared_history=[float(x) for x in manager.inv.chi2History])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fig, ax = plt.subplots(figsize=(12, 4.5))
    manager.showResult(ax=ax, cMap="Spectral_r", logScale=True,
                       label="Resistivity (ohm m)")
    ax.set_title(f"Wenner inversion: {survey.size()} measurements; relative RMS {summary['relative_rms_percent']:.2f}%")
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Elevation relative to surface (m)")
    fig.tight_layout()
    fig.savefig(args.output / "inversion.png", dpi=160)
    fig.savefig(args.output / "inversion.svg")
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
