"""Validated, flat-surface 2D ERT input and an isolated pyGIMLi worker."""
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

COLUMNS = ('ax', 'bx', 'mx', 'nx', 'rhoa', 'error')
PRESETS = {'Smooth model': False, 'Blocky model (IRLS)': True}


@dataclass(frozen=True)
class Settings:
    preset: str = 'Smooth model'
    regularization: float = 20.0
    max_iterations: int = 10
    start_resistivity: float = 100.0

    def validate(self):
        if self.preset not in PRESETS:
            raise ValueError('Choose a supported inversion preset.')
        if not math.isfinite(self.regularization) or self.regularization <= 0:
            raise ValueError('Regularization must be finite and positive.')
        if not math.isfinite(self.start_resistivity) or self.start_resistivity <= 0:
            raise ValueError('Starting resistivity must be finite and positive.')
        if type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 100:
            raise ValueError('Iteration limit must be between 1 and 100.')


def load_csv(path):
    """Coordinates in metres, rhoa in ohm m, relative error as a fraction."""
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not set(COLUMNS) <= set(reader.fieldnames):
            raise ValueError('CSV requires columns: ' + ', '.join(COLUMNS))
        for line, raw in enumerate(reader, 2):
            try:
                row = {key: float(raw[key]) for key in COLUMNS}
            except (ValueError, TypeError) as exc:
                raise ValueError(f'Line {line}: all required values must be numeric.') from exc
            if not all(math.isfinite(value) for value in row.values()):
                raise ValueError(f'Line {line}: non-finite value.')
            if len({row[key] for key in COLUMNS[:4]}) != 4:
                raise ValueError(f'Line {line}: four distinct finite electrodes required.')
            if row['rhoa'] <= 0 or not 0 < row['error'] < 1:
                raise ValueError(f'Line {line}: rhoa must be positive; error must be a fraction between 0 and 1.')
            # Flat half-space geometric factor denominator; zero cannot define rhoa.
            a, b, m, n = (row[key] for key in COLUMNS[:4])
            factor = 1 / abs(a-m) - 1 / abs(a-n) - 1 / abs(b-m) + 1 / abs(b-n)
            if abs(factor) < 1e-14:
                raise ValueError(f'Line {line}: degenerate electrode geometry.')
            rows.append(row)
    if not rows:
        raise ValueError('The survey contains no measurements.')
    return rows


def run_inversion(input_path, output_path, settings):
    settings.validate()
    rows = load_csv(input_path)
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import pygimli as pg
    from pygimli.physics import ert
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    data = pg.DataContainerERT()
    coordinates = sorted({row[key] for row in rows for key in COLUMNS[:4]})
    index = {x: data.createSensor([x, 0, 0]) for x in coordinates}
    for i, row in enumerate(rows):
        data.createFourPointData(i, *(index[row[key]] for key in COLUMNS[:4]))
    data['rhoa'] = [row['rhoa'] for row in rows]
    data['err'] = [row['error'] for row in rows]
    data['k'] = ert.createGeometricFactors(data)
    manager = ert.ERTManager(data, verbose=True)
    manager.invert(lam=settings.regularization, maxIter=settings.max_iterations,
                   startModel=settings.start_resistivity,
                   blockyModel=PRESETS[settings.preset], robustData=False, verbose=True)
    manager.saveResult(folder=str(output))
    fig, ax = plt.subplots(figsize=(10, 4))
    manager.showResult(ax=ax, logScale=True, label='Resistivity (ohm m)')
    fig.savefig(output / 'model.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    np.savetxt(output / 'observed_predicted.csv',
               np.column_stack((data['rhoa'], manager.inv.response, data['err'])),
               delimiter=',', header='observed_ohm_m,predicted_ohm_m,relative_error', comments='')
    (output / 'run.json').write_text(json.dumps({
        'settings': asdict(settings), 'pygimli_version': pg.__version__,
        'measurements': len(rows), 'chi_squared': float(manager.inv.chi2()),
        'relative_rms_percent': float(manager.inv.relrms()),
    }, indent=2), encoding='utf-8')
