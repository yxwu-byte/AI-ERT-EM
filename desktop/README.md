# ERT Studio desktop prototype

Windows-first desktop application for **2D, flat-surface ERT with finite electrodes**.
It runs pyGIMLi locally and offers smooth and blocky (IRLS) model regularization
presets. These are two configurations of the same inversion backend, not two
independent inversion engines. SimPEG is a future backend.

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
(e.g. `0.03` means 3%, not `3`). The importer does not infer units or convert voltages.
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
Partial output is retained on failure/cancellation; `run.json` marks a completed run.
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

- `ERTStudio-0.2.0-Windows-x64-Setup.exe`: per-user installer, Start-menu shortcut,
  optional desktop shortcut, and an uninstaller. No administrator access required.
- `ERTStudio-0.2.0-Windows-x64-Portable.zip`: extract the entire folder and
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
The included sample is available through **Try the included sample survey**.

## Checks

```powershell
python -m unittest discover -s desktop/tests -v
python desktop/app.py --smoke-test
```

The second command opens and closes the interface for a smoke check. Headless Linux
can set `QT_QPA_PLATFORM=offscreen`. Scientific verification also requires a real
synthetic inversion, separately from these parser checks.

## Next milestones

1. Native/instrument imports, topography and interactive quality-control plots.
2. Mesh preview, sensitivity/coverage view, convergence graphs and run comparison.
3. Project save/reopen and a registry for additional inversion backends.
4. Natural-language assistant using explicit application actions and project state.
5. Clean Windows packaging checks and installer release.

## Verification in this workspace

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
Windows DLLs were inspected and are explicitly collected, but Windows installer
execution remains pending a Windows CI run.

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
