# ERT Studio desktop prototype

Windows-first desktop application for **2D, flat-surface ERT with finite electrodes**.
It runs pyGIMLi locally and offers smooth and blocky (IRLS) model regularization
presets. These are two configurations of the same inversion backend, not two
independent inversion engines. Optional SimPEG and PyHydroGeophysX packs add
additional engines without enlarging the base installer.

## Run on Windows

Use 64-bit Python 3.12. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r desktop\requirements.txt
.\.venv-desktop\Scripts\python.exe desktop\app.py
```

Development on Linux uses the equivalent venv Python. GUI needs Qt system libraries.
The pyGIMLi compiled core must have a compatible binary for the selected Python/OS.

## Input contract

CSV header: `ax,bx,mx,nx,rhoa,error`. Coordinates are horizontal positions in metres;
all electrodes have elevation zero. `rhoa` is positive apparent resistivity in
**ohm metres**; `error` is a relative standard deviation expressed as a **fraction**
(e.g. `0.03` means 3%, not `3`). This is the internal interchange contract. The conversion dialog accepts
other column names, units and voltage/current or resistance measurements.
A/B are current electrodes, M/N are potential electrodes. All four must be distinct.
Remote electrodes and topography are unsupported in this prototype.

```csv
ax,bx,mx,nx,rhoa,error
0,3,1,2,100,0.03
1,4,2,3,105,0.03
2,5,3,4,98,0.03
```

This three-row snippet demonstrates the format; use a sufficiently sampled survey
for meaningful inversion. Supply realistic error estimates. Input checks are not
a full data-quality assessment; no reciprocal filtering is implemented yet.

## Workflow and results

Import → Check data → Configure inversion → Run → Review results.
Choose a parent output folder: every run creates a unique `ert-run-*` directory,
with a snapshot of the imported measurements and selected settings. Configuration
is locked during a run. The worker runs separately and cancellation terminates it.
Partial output is retained on failure/cancellation. `batch.json` records engine
statuses; each engine directory contains `run.json` only after successful completion.
Outputs include a model image, observed/predicted CSV, pyGIMLi mesh/coverage exports,
backend version, chi-squared and relative RMS. An iteration limit is not evidence
of convergence. Review the solver log and diagnostics.

The sidebar supports explicit navigation commands, including `go to import`,
`check data`, `configure inversion`, `run inversion` and `show results`.
It **does not yet contain a language model** and never launches inversion through chat.
There are no network requests or API credentials in this application.

## Standalone Windows distribution

Version 0.1.0 passed Windows executable and installer checks. Version 0.2.0 adds
workflow tiles and expanded inversion controls. See PR #2 for the latest successful
Windows build and downloads.

The Windows build produces two downloads:

- `ERTStudio-0.3.0-Windows-x64-Setup.exe`: per-user installer, Start-menu shortcut,
  optional desktop shortcut, and an uninstaller. No administrator access required.
- `ERTStudio-0.3.0-Windows-x64-Portable.zip`: extract the entire folder and
  double-click `ERTStudio.exe`. Keep `_internal` beside the executable.

Users do not install Python, scientific packages, or an API key. Inversion is offline.
These are unsigned preview builds for 64-bit Windows 10/11.

The GitHub Actions workflow `.github/workflows/windows-desktop.yml` builds on
Windows, checks the frozen GUI and real inversions, builds the installer, installs
it into a separate directory and checks the installed executable again. It uploads
both downloads and SHA256 checksums as `ERTStudio-Windows-x64`. Download the artifact
from a successful workflow run and extract its outer ZIP to get the installer and
portable ZIP. Artifacts expire after 30 days; no public release is created.

### Build on Windows yourself

From the repository root using the development environment above:

```powershell
.\.venv-desktop\Scripts\python.exe -m pip install -r desktop\packaging\requirements-build.txt
.\.venv-desktop\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\packaging\ertstudio.spec
.\.venv-desktop\Scripts\python.exe desktop\packaging\collect_licenses.py dist\ERTStudio\third-party-licenses
.\.venv-desktop\Scripts\python.exe desktop\packaging\verify_bundle.py dist\ERTStudio\ERTStudio.exe
```

The CI workflow also includes application source, full installed dependency license
metadata and notices, and then uses Inno Setup 6 with `desktop/packaging/installer.iss`
to build the installer. See the workflow for the complete release assembly sequence.

The packager explicitly collects pyGIMLi's native solver DLLs. Worker logs are
written to `solver.log` and displayed in the GUI even in a windowed executable.
Caches use a writable per-user folder instead of the installation directory.
Startup errors are logged to `%LOCALAPPDATA%/ERTStudio/startup-error.log`.
Choose a synthetic survey in the sample library, then click **Load selected sample**.

## Checks

```powershell
python -m unittest discover -s desktop/tests -v
python desktop/app.py --smoke-test
```

The second command opens and closes the interface for a smoke check. Headless Linux
can set `QT_QPA_PLATFORM=offscreen`. Scientific verification also requires a real
synthetic inversion, separately from these parser checks.

## Next milestones

1. Additional instrument formats, topography and interactive quality-control plots.
2. Mesh preview, sensitivity/coverage views and convergence graphs.
3. Project save/reopen and more backend-specific inversion algorithms.
4. Natural-language assistant using explicit application actions and project state.
5. Signed releases and longer-lived distribution links.

## Initial prototype verification (historical)

Validated on Linux with Python 3.12: three input/settings test cases passed; Qt
opened and closed using the offscreen platform. Both presets completed a
35-measurement homogeneous 100 ohm m survey starting at 80 ohm m, with χ² ≈ 0.399
and relative RMS ≈ 1.93%. The actual `app.py --worker` entry point also completed,
and its model image was inspected. Both runs stopped after one update, so this
check does not establish differences between IRLS and smooth regularization.
The input is available at `desktop/examples/homogeneous.csv`. These are basic
operation checks, not field validation or a Windows executable test.

The standalone packaging was also frozen and checked on Linux: the bundled GUI
opened, the guided import → worker → result-image workflow completed, both solver
presets produced valid exports, and invalid input returned failure with a saved
log. Checks used a separate working directory containing spaces and Unicode.
Windows versions 0.1 and 0.2 subsequently passed executable and installer tests.
The version 0.3 workflow additionally verifies optional solver packs and conversions.

## Version 0.2: visual workflow and inversion controls

All five steps are visible as clickable tiles across the main workspace; the
selected tile opens its page underneath. The chat sidebar remains available.
The configuration page groups parameters into model/regularization, data
weighting, mesh, resistivity bounds, and stopping criteria, with tooltips and a
Restore recommended defaults button.

| Control | Default | Meaning |
|---|---|---|
| Model preset | Smooth | Smooth or blocky model regularization |
| Regularization λ | 20 | Strength of the roughness penalty |
| Starting resistivity | 100 ohm m | Uniform initial model |
| Vertical smoothing weight | 1 | Vertical / horizontal roughness weight; smaller permits more vertical change |
| λ multiplier per iteration | 1 | Values below 1 relax regularization each iteration |
| Robust data weighting | Off | IRLS downweighting of large data residuals, independent of blocky model regularization |
| Minimum relative error | CSV errors | Percentage floor; effective error = max(CSV fraction, percentage / 100) |
| Mesh depth | Automatic | Parameter domain depth in metres, not a depth-of-investigation estimate |
| Maximum parameter cell area | Automatic | Triangle area in m²; smaller values increase cost |
| Resistivity bounds | Off | Positive lower/upper model bounds; start must lie strictly inside |
| Maximum iterations | 10 | Maximum solver updates |
| Minimum objective improvement | 1% | Relative objective-change stopping criterion |
| Stop at χ² ≤ 1 | On | Stop when data fit is consistent with the assigned errors |

The run metadata records the selected settings and the options forwarded to
pyGIMLi. Exported data-fit CSVs contain the effective errors after applying the
optional floor. Old four-field settings files still load with defaults for the
new controls. The guided GUI check clicks every tile, checks chat navigation and
default restoration, then completes an inversion with non-default controls and
checks error-floor propagation and resistivity bounds.

## Version 0.3: sample library, format conversion and optional engines

The app includes four synthetic surveys (homogeneous, conductive target,
resistive target, layered ground) and equivalent files for learning conversion.
See `examples/README.md`. Import standard CSV, delimited text with column mapping,
BERT electrode/data `.ohm` files or RES2DINV Wenner alpha `.dat` files. The mapping
dialog handles electrode IDs with a separate `id,x` table; metres/centimetres/feet;
apparent resistivity, resistance or voltage/current; V/mV and A/mA; fractional or
percentage errors. Preview the conversion before acceptance. Missing errors need
an explicitly selected fallback estimate. All results use the same canonical
`ax,bx,mx,nx,rhoa,error` schema. Export the converted CSV and its mapping report;
each batch also preserves that report. Unsupported topography and invalid rows
are rejected, not silently flattened or dropped.

### Select one engine or several

- **pyGIMLi** is included in the base app and supports smooth/blocky regularization.
- **SimPEG 0.25.2** is an optional self-contained worker using a 2.5D nodal DC
  simulation, tensor mesh, L2 log-resistivity regularization and ProjectedGNCG.
- **PyHydroGeophysX 0.3.0** is an optional worker built from the bundled upstream
  source, using its ERT inversion loop and pyGIMLi forward modelling. Its CGLS or
  LSQR linear solver is selectable. This is not an independent forward solver.

The main installer excludes SimPEG, PyHydroGeophysX and their extra dependencies.
GitHub Actions builds and hosts optional packs separately. In Configure inversion,
click **Get optional engine packs from GitHub**. On the latest successful Windows
build, download `ERTEngine-simpeg` or `ERTEngine-hydro` from Artifacts. Extract the
outer GitHub artifact ZIP, then click **Install downloaded engine-pack ZIP** and
select the contained `ERTEngine-...-Windows-x64.zip`. Only use packs from the linked
repository's builds. Packs are stored under `%LOCALAPPDATA%/ERTStudio/engines`.
Their protocol/platform, paths and SHA256 file manifest are checked before an
atomic installation. GitHub sign-in may be required; artifacts expire in 30 days.

Select any available checkboxes and run. The engines execute sequentially in
separate processes, with one result directory each. The Results page shows a
comparison table and a model selector. Per-engine failures do not discard other
completed runs. Cancel stops the active and pending jobs while retaining completed
outputs. Optional packs need disk space only when installed; the same installed
pack works with both portable and installed copies of the application.

**GitHub hosts the engine downloads; it does not run the surveys remotely.**
No token, upload or internet access is needed for inversion after installing the
chosen packs. Linking to a source repository alone cannot execute a solver.

### Comparing results responsibly

Every engine receives the same canonical measurement order and error floor.
`comparison.csv` and `comparison_metrics.json` use the common metric
`mean(((log(predicted_rhoa)-log(observed_rhoa))/log1p(relative_error))**2)` and
relative apparent-resistivity RMS (%). The native objective, mesh and definition
of regularization differ across engines, so the same λ is not equivalent.
The minimum residual alone does not identify the best geological model.

Mesh depth, cell size/area, start, bounds, λ, λ multiplier, errors and iteration
limit are passed through the adapters. PyGIMLi's blocky/robust/vertical-weight and
stopping controls are clearly labeled as pyGIMLi-only. SimPEG uses smooth L2
regularization, its native voltage-data misfit target and optimizer stopping.
PyHydroGeophysX uses its upstream fixed stopping rule (χ² < 1.5 or < 1% change)
and supports its own linear-solver selector. Adapter options are recorded in each
run's `run.json`. The adapters do not pretend unsupported settings are applied.

### Build and verification

The Windows workflow builds the optional workers in isolated jobs with only their
own dependencies. It verifies each frozen worker before packaging it. The base
job installs both packs through the same validator used by the GUI and runs the
three-engine workflow against the portable application and again after a silent
installation. Conversion checks exercise the actual mapping dialog, all five input
representations, sample validation, unit/error conversions and exports. Unit tests
also reject corrupt/unsafe packs and invalid geometry/data.
