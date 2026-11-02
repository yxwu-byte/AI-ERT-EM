"""Metrics shared across engines; native objectives are deliberately kept separate."""
from dataclasses import asdict
from pathlib import Path
import json


def write_comparison_metrics(output, rows, predicted, settings):
    import numpy as np
    observed = np.asarray([row['rhoa'] for row in rows])
    errors = np.asarray([max(row['error'], settings.error_floor) for row in rows])
    predicted = np.asarray(predicted).reshape(-1)
    if predicted.shape != observed.shape or not np.isfinite(predicted).all() or not np.all(predicted > 0):
        raise ValueError('Engine returned invalid apparent resistivity predictions.')
    metrics = dict(common_log_chi_squared=float(np.mean(((np.log(predicted)-np.log(observed))/np.log1p(errors))**2)),
                   relative_rms_percent=float(100*np.sqrt(np.mean(((predicted-observed)/observed)**2))))
    (Path(output)/'comparison_metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False),encoding='utf-8')
    np.savetxt(Path(output)/'observed_predicted.csv', np.column_stack((observed,predicted,errors)), delimiter=',',
               header='observed_ohm_m,predicted_ohm_m,relative_error',comments='')
    return metrics


def finish_run(output, rows, predicted, settings, backend, version, options):
    metrics = write_comparison_metrics(output,rows,predicted,settings)
    # chi_squared is the common, explicitly defined log-data metric here.
    result = dict(settings=asdict(settings), backend=backend, backend_version=version,
                  measurements=len(rows), inversion_options=options,
                  chi_squared=metrics['common_log_chi_squared'], **metrics)
    (Path(output)/'run.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result
