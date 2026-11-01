# AI-ERT-EM

## Run in GitHub Codespaces

1. Open this repository on GitHub, select **Code → Codespaces → Create codespace on main**.
2. Wait for setup to install pyGIMLi and run the ERT example automatically.
3. In the Codespaces terminal, run:

   ```bash
   source .venv/bin/activate
   python examples/ert_forward.py
   ```

The example computes apparent resistivity for a homogeneous 100 ohm-m
half-space and checks the results. The **Actions** tab runs the same check
on pushes and pull requests; it can also be started manually.

Create a `.ipynb` notebook in the Codespaces editor and select the `.venv`
Python kernel to work interactively. Codespaces availability and usage limits
depend on your GitHub account.

## Run locally

Use Python 3.12 from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python examples/ert_forward.py
```

These workflows install the published pyGIMLi package and its compiled core.
Changes to the source snapshot below require a separate source build to take
effect in the installed package.

## pyGIMLi source

The `pygimli-source/` directory contains an unmodified source snapshot of
[pyGIMLi](https://www.pygimli.org), a library for geophysical modelling and inversion.

- Upstream repository: https://github.com/gimli-org/gimli
- Release: `v1.6.1`
- Upstream commit: `362b69893f5abcacb0b36cbfff2934605ecfe3f2`
- License: Apache 2.0; see [LICENSE.md](pygimli-source/LICENSE.md).
  Included third-party components retain their original license notices.

The copy includes the Python package, C++ core, examples, documentation, and
build configuration. It is a source snapshot without upstream Git history.
See [installation instructions](pygimli-source/INSTALLATION.md) and
[upstream README](pygimli-source/README.md) for usage and build guidance.

The imported Git tree was verified to match the upstream Git tree exactly,
including all file contents and modes. Upstream Git attributes control
checkout line endings. Downloading the source does not install or compile pyGIMLi.

## SimPEG ERT and EM inversions

The [SimPEG/](SimPEG/) subfolder contains SimPEG 0.25.2 source, official tutorial data, reproducible setup scripts, and saved results from ten synthetic ERT, time-domain EM, and frequency-domain EM inversions. Eight upstream EM sensitivity tests passed.

Start with the [SimPEG setup instructions](SimPEG/README.md) and [inversion test report with figures](SimPEG/REPORT.md). SimPEG uses its own virtual environment inside that subfolder.

## PyHydroGeophysX source and ERT inversion

The [PyHydroGeophysX/](PyHydroGeophysX/) folder contains Hang Chen's v0.3.0
source snapshot, its Apache 2.0 license, setup instructions, and a synthetic
ERT inversion example. Its setup installs the bundled source into a separate
virtual environment and builds a Python wheel. Start with the
[workspace instructions](PyHydroGeophysX/README.md).

The separate ERT-data automatic processing repository installs the published
PyHydroGeophysX 0.3.0 package from PyPI. This source copy is available for local
development; adding it here does not change that pipeline's dependency source.

## Windows-first ERT desktop prototype

[ERT Studio](desktop/README.md) adds a Qt desktop interface with visual workflow tiles and expanded inversion controls for flat-surface
2D surveys, CSV validation, pyGIMLi smooth/blocky presets, background inversion,
results export and an offline command-based navigation sidebar. A Windows CI build
produces a bundled executable, portable ZIP and per-user installer, with packaged
GUI and inversion checks. See the desktop documentation for build status and downloads.

Version 0.3 adds four synthetic sample surveys, a column/unit mapping and format
conversion workflow, and optional SimPEG / PyHydroGeophysX solver packs hosted
by GitHub Actions. Users can select one or several local engines and compare
common apparent-resistivity fit metrics without bundling all engines in the base app.
