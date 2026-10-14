#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -m venv .venv
export PIP_CACHE_DIR="$PWD/.cache/pip"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
.venv/bin/python -m pip install -r requirements-dependencies.txt
# The override allows installing the bundled source even without Git metadata.
SETUPTOOLS_SCM_PRETEND_VERSION_FOR_SIMPEG=0.25.2 .venv/bin/python -m pip install -e ./source
.venv/bin/python -m pip check
