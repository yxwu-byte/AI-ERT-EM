#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
mkdir -p logs
export MPLBACKEND=Agg
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
.venv/bin/python -m pip check
for method in ert tdem fdem; do
    echo "Running official $method tutorials (see logs/$method.log)"
    .venv/bin/python -u run_examples.py "$method" > "logs/$method.log" 2>&1
done
for method in fdem tdem; do
    echo "Running $method instrument-style demonstration"
    .venv/bin/python -u examples/instrument_style.py "$method" > "logs/${method}_instrument_style.log" 2>&1
done
.venv/bin/python -m pytest -q source/tests/em/em1d/test_EM1D_FD_getJ.py source/tests/em/em1d/test_EM1D_TD_getJ.py > logs/jacobian-tests.log 2>&1
.venv/bin/python verify_results.py
.venv/bin/python build_report.py
echo "Finished. See REPORT.md and results/."
