# PyHydroGeophysX source workspace

This folder contains Hang Chen's **PyHydroGeophysX v0.3.0** source, an isolated
installation script, and a small synthetic ERT inversion example. It follows
the repository's SimPEG workspace layout.

- Upstream: <https://github.com/geohang/PyHydroGeophysX>
- Release commit: `311b1b4c87ede8aabdf6a7a38d4f05d992d20298`
- License: Apache 2.0; retain [the upstream license](source/LICENSE) and attribution.
- [provenance.json](provenance.json) records every included and omitted upstream
  file. All retained files have their original Git blob contents. The upstream
  `Ex_multi_agent_workflow.ipynb` notebook is omitted because GitHub push protection
  detected an embedded API key. Large
  `examples/data/` datasets and generated notebook checkpoints are omitted.
  Download the matching upstream release to run examples that need those data.
  The example below generates its own data.

`source/` is a regular source directory, without nested Git history or a Git
submodule. Cloning this repository or downloading its ZIP includes the code.
Upstream updates must be imported deliberately; they do not appear automatically.

## Install and use

Use Python **3.12**. From this folder on Linux/macOS:

```bash
bash setup.sh
source .venv/bin/activate
python run_ert_example.py
```

Setup creates this folder's `.venv`, installs pinned ERT dependencies, installs
**the bundled source in editable mode**, byte-compiles its Python modules,
checks dependencies, and builds a wheel under `dist/`. Source edits take effect
in this environment. The initial dependency installation needs internet access.
The synthetic example needs no downloads or AI API key and writes model/data
CSV, VTK, a figure, the input survey, and fit metrics under `results/ert/`.
Rerunning the example overwrites that output directory's named files.

PyHydroGeophysX itself is Python code; it does not require a separate C++
compilation. ERT uses pyGIMLi's compiled numerical core, installed as a published
dependency. The setup does not rebuild that core from `../pygimli-source/`.

For Windows PowerShell, use the equivalent commands from this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dependencies.txt
python -m pip install --no-build-isolation --no-deps -e ./source
python -m pip check
python -m compileall -q source/PyHydroGeophysX
python -m pip wheel --no-build-isolation --no-deps ./source --wheel-dir dist
python run_ert_example.py
```

Linux is the validated platform for the saved run. Other platforms need
compatible pyGIMLi/pgcore wheels. Recreate the environment on each machine;
virtual environments are not portable. Optional GUI, hydrology, GPU, AI-agent,
SimPEG-based EM, and other integrations need their own dependencies; see
[upstream packaging metadata](source/pyproject.toml) and
[upstream documentation](source/README.md). This setup verifies CPU ERT only.

## Relationship to ERT-data automatic processing

The separate `yxwu-byte/ERT-data` workflow currently installs
`PyHydroGeophysX==0.3.0` **from PyPI** using pip. Each worker uses its installed
package for inversion; inversion does not browse or call the developer's GitHub
repository. Its ERT forward modelling uses pyGIMLi.

You do not need a copy in your GitHub repository to run that published package.
Keeping this snapshot is useful for inspection, modifications, and retaining
the source version. Adding it here does not change ERT-data's installation.
To use future local modifications in automatic processing, explicitly change
ERT-data to install a built wheel or this source at a pinned repository commit.

See [VALIDATION.md](VALIDATION.md) for the saved build and inversion checks.
