#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -m venv .venv
export PIP_CACHE_DIR="$PWD/.cache/pip"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export XDG_CONFIG_HOME="$PWD/.cache/config"
.venv/bin/python -m pip install -r requirements-dependencies.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e ./source
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q source/PyHydroGeophysX
.venv/bin/python -m pip wheel --no-build-isolation --no-deps ./source --wheel-dir dist
