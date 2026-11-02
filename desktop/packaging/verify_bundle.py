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
invoke(['--assistant-test', output / 'assistant checks'])
invoke(['--conversion-test', output / 'conversion checks'])
invoke(['--workflow-test', output / 'guided workflow'])
guided_runs = list((output / 'guided workflow').glob('ert-run-*/pygimli/run.json'))
assert guided_runs, 'GUI worker did not finish'
guided = json.loads(guided_runs[0].read_text())
assert guided['settings']['error_floor'] == 0.05
assert guided['inversion_options']['limits'] == [50, 200]
assert guided['inversion_options']['robustData'] is True
assert guided['inversion_options']['paraDepth'] == 4
assert guided['inversion_options']['paraMaxCellSize'] == 0.5
with (guided_runs[0].parent / 'observed_predicted.csv').open() as stream:
    assert all(abs(float(row['relative_error']) - 0.05) < 1e-12 for row in csv.DictReader(stream))
model = next(guided_runs[0].parent.rglob('resistivity.vector'))
values = [float(line) for line in model.read_text().split()]
assert all(50 <= value <= 200 for value in values)
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

if len(sys.argv) > 3 and sys.argv[3] == '--with-engines':
    invoke(['--multi-test', output / 'multiple engines'])
    batches = list((output / 'multiple engines').glob('ert-run-*/batch.json'))
    assert len(batches) == 1
    batch = json.loads(batches[0].read_text())
    assert set(batch) == {'pygimli','simpeg','hydro'}
    assert all(item['status'] == 'completed' for item in batch.values())
    assert all(math.isfinite(item['common_log_chi_squared']) and item['relative_rms_percent'] < 8 for item in batch.values())
    assert (batches[0].parent / 'comparison.csv').is_file()
