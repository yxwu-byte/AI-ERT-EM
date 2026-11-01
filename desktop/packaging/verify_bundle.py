"""Exercise the executable, not the developer's Python imports."""
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

exe = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parents[1] / 'examples' / 'homogeneous.csv'
output = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix='ert-verification-'))
output.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
for key in ('PYTHONPATH', 'PYTHONHOME'):
    env.pop(key, None)
env['QT_QPA_PLATFORM'] = 'offscreen'


def invoke(args):
    result = subprocess.run([str(exe), *map(str, args)], cwd=output, env=env, timeout=180, capture_output=True)
    if result.returncode:
        logs = '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in output.rglob('solver.log'))
        raise RuntimeError(f'Executable failed ({result.returncode}): {result.stderr!r}\n{logs}')


invoke(['--diagnostics', output / 'diagnostics.json'])
diagnostics = json.loads((output / 'diagnostics.json').read_text())
assert diagnostics['frozen'], 'Verification must use the packaged executable'
invoke(['--smoke-test'])
invoke(['--workflow-test', output / 'guided workflow'])
assert list((output / 'guided workflow').glob('ert-run-*/run.json')), 'GUI worker did not finish'
for preset, name in [('Smooth model', 'smooth'), ('Blocky model (IRLS)', 'blocky')]:
    run = output / f'{name} run ü'
    run.mkdir(exist_ok=True)
    shutil.copy2(source, run / 'survey.csv')
    (run / 'settings.json').write_text(json.dumps(dict(preset=preset, regularization=20,
        max_iterations=5, start_resistivity=80)), encoding='utf-8')
    invoke(['--worker', run])
    result = json.loads((run / 'run.json').read_text())
    assert result['measurements'] == 35
    assert math.isfinite(result['chi_squared']) and result['chi_squared'] < 1
    assert 0 <= result['relative_rms_percent'] < 5
    assert (run / 'model.png').stat().st_size > 10000
    assert list(run.rglob('*.vtk')), 'Mesh export missing'
    with (run / 'observed_predicted.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 35
    assert all(math.isfinite(float(row['predicted_ohm_m'])) and float(row['predicted_ohm_m']) > 0 for row in rows)
# Broken input must return nonzero rather than report success.
bad = output / 'invalid'
bad.mkdir(exist_ok=True)
(bad / 'settings.json').write_text('{}')
(bad / 'survey.csv').write_text('bad,input\n')
result = subprocess.run([str(exe), '--worker', str(bad)], cwd=output, env=env, timeout=30)
assert result.returncode != 0 and not (bad / 'run.json').exists()
assert 'ValueError' in (bad / 'solver.log').read_text(encoding='utf-8')
print(f'Packaged GUI, both inversions, exports and invalid-input handling passed: {output}')
