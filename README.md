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
