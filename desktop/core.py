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

    robust_data: bool = False
    vertical_weight: float = 1.0
    lambda_factor: float = 1.0
    min_phi_change: float = 1.0
    stop_at_chi_one: bool = True
    error_floor: float = 0.0
    mesh_depth: float | None = None
    max_cell_area: float | None = None
    lower_resistivity: float | None = None
    upper_resistivity: float | None = None
    hydro_solver: str = 'cgls'

    def validate(self):
        if self.hydro_solver not in ('cgls','lsqr'):
            raise ValueError('Unsupported PyHydroGeophysX linear solver.')
        if self.preset not in PRESETS:
            raise ValueError('Choose a supported inversion preset.')
        if not math.isfinite(self.regularization) or self.regularization <= 0:
            raise ValueError('Regularization must be finite and positive.')
        if not math.isfinite(self.start_resistivity) or self.start_resistivity <= 0:
            raise ValueError('Starting resistivity must be finite and positive.')
        if type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 100:
            raise ValueError('Iteration limit must be between 1 and 100.')

        for name in ('vertical_weight', 'lambda_factor'):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f'{name} must be between 0 (exclusive) and 1.')
        if not math.isfinite(self.min_phi_change) or not 0 <= self.min_phi_change <= 100:
            raise ValueError('Minimum objective improvement must be between 0 and 100%.')
        if not math.isfinite(self.error_floor) or not 0 <= self.error_floor < 1:
            raise ValueError('Error floor must be a fraction from 0 to less than 1.')
        for name in ('mesh_depth', 'max_cell_area'):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f'{name} must be positive or automatic.')
        if (self.lower_resistivity is None) != (self.upper_resistivity is None):
            raise ValueError('Specify both resistivity bounds or neither.')
        if self.lower_resistivity is not None:
            low, high = self.lower_resistivity, self.upper_resistivity
            if not all(math.isfinite(v) for v in (low, high)) or not 0 < low < self.start_resistivity < high:
                raise ValueError('Bounds must satisfy 0 < minimum < starting resistivity < maximum.')
        if type(self.robust_data) is not bool or type(self.stop_at_chi_one) is not bool:
            raise ValueError('Robust data and chi-squared stopping options must be boolean.')

    def inversion_options(self):
        self.validate()
        options = dict(lam=self.regularization, maxIter=self.max_iterations,
                       startModel=self.start_resistivity, blockyModel=PRESETS[self.preset],
                       robustData=self.robust_data, zWeight=self.vertical_weight,
                       lambdaFactor=self.lambda_factor, dPhi=self.min_phi_change,
                       stopAtChi1=self.stop_at_chi_one, verbose=True)
        if self.mesh_depth is not None:
            options['paraDepth'] = self.mesh_depth
        if self.max_cell_area is not None:
            options['paraMaxCellSize'] = self.max_cell_area
        if self.lower_resistivity is not None:
            options['limits'] = [self.lower_resistivity, self.upper_resistivity]
        return options


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


def run_inversion(input_path, output_path, settings, backend='pygimli'):
    import importlib
    if backend not in ('pygimli','simpeg','hydro'):
        raise ValueError('Unknown inversion engine.')
    return importlib.import_module('backend_' + backend).run(input_path, output_path, settings)
