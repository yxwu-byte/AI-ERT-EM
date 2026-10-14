# SimPEG inversion workspace

SimPEG **0.25.2** is installed and tested in this folder, under `AI-ERT-EM`, in the connected **Linux cloud workspace**. This GitHub folder contains the source snapshots, scripts, and saved results; run the setup below to create an environment on your machine. The laptop's local Python installation was not changed. See [REPORT.md](REPORT.md) for measured results.

SimPEG is a Python package. Its editable installation was built from the official source, its Python modules were byte-compiled, and a distributable wheel was built in `dist/`. Scientific dependencies, including the compiled discretize and geoana components, were installed from published packages. An additional C/C++ compilation of SimPEG itself is not required.

## Use the installed environment

From this folder:

```bash
source .venv/bin/activate
python -c "import simpeg; print(simpeg.__version__)"
python run_examples.py ert
python run_examples.py tdem
python run_examples.py fdem
python examples/instrument_style.py fdem
python examples/instrument_style.py tdem
python verify_results.py
```

`bash run_all.sh` repeats all examples and the eight upstream Jacobian checks, saving console output under `logs/`. It takes a few minutes on the tested machine. The official runs use local data, headless plotting, and seeded beta estimation; they do not need network access once installed. Re-running overwrites result files for that method. `REPORT.md` records the verified run. The complete runner writes new summaries to `results/*/summary.json` and regenerates the report.

## Recreate on another machine

Keep the source, tutorial assets, and scripts together. Python 3.12 was tested; SimPEG requires Python 3.11 or newer. For Linux/macOS, `bash setup.sh` creates a fresh virtual environment and installs pinned dependencies plus the bundled source. Internet access is needed to obtain dependencies and build tooling. A cloud virtual environment cannot be copied to macOS or Windows and used directly.

Alternatively, install the built wheel into your own environment:

```bash
python -m venv .venv
# Activate the environment using your operating system's usual command.
python -m pip install -r requirements-dependencies.txt
python -m pip install dist/simpeg-0.25.2-py3-none-any.whl
python -m pip check
```

On Windows, use `py -3.12 -m venv .venv` and `.venv\Scripts\Activate.ps1` in PowerShell. The Python example commands work after activation; the shell scripts require Bash.

## Contents

| Path | Contents |
| --- | --- |
| `source/` | Official SimPEG v0.25.2 source snapshot and examples |
| `user-tutorials/` | Official tutorial snapshot pinned to a recorded Git commit, including data |
| `.venv/` | Isolated, working Linux Python environment |
| `dist/` | Built SimPEG wheel |
| `examples/*_upstream.py` | Original code cells extracted from official notebooks |
| `examples/*_local.py` | Code cells adapted for local archives and deterministic beta estimates |
| `run_examples.py` | Tutorial runner; captures each inversion and saves headless figures |
| `examples/instrument_style.py` | Additional synthetic multi-coil FDEM and finite-waveform TDEM examples |
| `results/` | PNG figures, NPZ arrays, CSV models/data fits, meshes, JSON metrics, input files |
| `logs/` | Installation, build, inversion, and upstream test logs |
| `requirements-lock.txt` | Full installed package freeze with source commit |
| `requirements-dependencies.txt` | Pinned dependencies without an absolute editable source path |
| `provenance.json` | Versions, commits, checksums, and build metadata |

## Result conventions

Weighted RMS is `sqrt(mean(((predicted - observed) / standard_deviation)**2))`; values around one indicate fit at the assigned error level. Successful fitting does not establish a unique model or validate real instrument calibration.

The official ERT example performs 2.5D forward modelling of a 2D model with topography: inversion 1 stores log-conductivity (S/m), and inversion 2 stores log-resistivity (ohm m). Active-cell masks and mesh coordinates are saved with the NPZ files. Convert with `exp(model)` for conductivity in inversion 1 and `exp(model)` for resistivity in inversion 2.

For official EM inversion 1 (smooth) and 2 (sparse), parameters are log-conductivity (S/m) in layer order from the surface downward. `layer_thicknesses` excludes the bottom half-space. Inversion 3 has five logarithmic parameters: the two layer thicknesses (m) followed by three layer resistivities (ohm m). Its saved `layer_thicknesses` is the recovered pair. Conductivities are `1 / exp(recovered_model[2:])`. See the official notebook's `Wires` mappings for details. Instrument-style examples invert three log-conductivities with fixed layer thicknesses; their CSV files already contain conductivities in S/m.

## Applying this to your instruments

The official examples use synthetic tutorial observations. The instrument-style examples use illustrative geometries and synthetic noise; they are starting points for survey definitions, rather than validated SkyTEM, tTEM, or CMD Mini-Explorer configurations.

For tTEM/SkyTEM, supply the transmitter geometry, turns/current, low/high-moment waveforms, turn-off timing, receiver offset/orientation/heights, gate windows and their averaging, data units, and uncertainties. The extra TDEM example includes a finite waveform and a dB/dt receiver, but samples individual gate-center times rather than integrating actual instrument windows.

For CMD Mini-Explorer, confirm the model/version, frequency, coil separations, orientations and height, and whether exports contain apparent conductivity, in-phase, or quadrature. The extra FDEM example models secondary/primary magnetic field in ppm; conversion to apparent conductivity requires the instrument convention. Its vertical and horizontal dipoles illustrate two coplanar configurations, with both in-phase and quadrature channels. Real surveys may provide fewer independent channels and weaker depth constraints.

Other examples retained in the official source include a 3D ERT two-sphere inversion, a 3D forward/2D model loop-loop FDEM inversion, and cylindrical TDEM with a VTEM waveform. These larger examples were not run in this task.

SimPEG is distributed under the MIT license; see `source/LICENSE`. Preserve upstream licenses when redistributing the bundled source and tutorials.

The `source/` and `user-tutorials/` folders are regular source snapshots without nested Git history. Their upstream commits are recorded in `provenance.json`. A normal Git clone or GitHub ZIP download includes both snapshots.
