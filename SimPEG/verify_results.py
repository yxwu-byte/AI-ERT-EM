"""Verify saved inversion arrays against their reported fit metrics."""
import json
from pathlib import Path
import numpy as np

root = Path(__file__).resolve().parent
count = 0
for method, expected in [("ert", 2), ("tdem", 3), ("fdem", 3),
                          ("tdem_instrument_style", 1), ("fdem_instrument_style", 1)]:
    directory = root / "results" / method
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["status"] == "passed", method
    records = summary.get("inversions", [summary])
    assert len(records) == expected, method
    for record in records:
        filename = f'inversion_{record["inversion"]}.npz' if "inversion" in record else "inversion.npz"
        with np.load(directory / filename) as saved:
            obs, pred, std = (saved[k] for k in ["observed", "predicted", "standard_deviation"])
            assert obs.shape == pred.shape == std.shape == (record["n_data"],)
            assert np.all(np.isfinite(obs)) and np.all(np.isfinite(pred))
            assert np.all(np.isfinite(std)) and np.all(std > 0)
            assert saved["recovered_model"].size == record["n_parameters"]
            assert np.all(np.isfinite(saved["recovered_model"]))
            rms = float(np.sqrt(np.mean(((pred - obs) / std)**2)))
            assert np.isclose(rms, record["final_weighted_rms"], rtol=1e-10)
            assert rms < record["initial_weighted_rms"] and rms < 1.5
            if "cell_centers" in saved:
                assert saved["active_cells"].sum() == record["n_parameters"]
            count += 1
    assert list(directory.glob("*.png")), method
print(f"PASS: {count} saved inversions across 5 examples; finite arrays, improved fits, WRMS < 1.5, figures present.")
