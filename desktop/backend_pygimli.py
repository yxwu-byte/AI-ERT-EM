from core import Settings, PRESETS, COLUMNS, load_csv
from dataclasses import asdict
from pathlib import Path
import json

def run(input_path, output_path, settings):
    settings.validate()
    rows = load_csv(input_path)
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import pygimli as pg
    from pygimli.physics import ert
    import matplotlib.pyplot as plt

    output = Path(output_path).resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = pg.DataContainerERT()
    coordinates = sorted({row[key] for row in rows for key in COLUMNS[:4]})
    index = {x: data.createSensor([x, 0, 0]) for x in coordinates}
    for i, row in enumerate(rows):
        data.createFourPointData(i, *(index[row[key]] for key in COLUMNS[:4]))
    data['rhoa'] = [row['rhoa'] for row in rows]
    data['err'] = [max(row['error'], settings.error_floor) for row in rows]
    data['k'] = ert.createGeometricFactors(data)
    manager = ert.ERTManager(data, verbose=True)
    manager.invert(**settings.inversion_options())
    # The Windows C++ mesh exporter does not accept Unicode absolute paths.
    # Python can enter the directory using wide-character OS calls; native
    # exports then use ASCII relative names. This runs in the isolated worker.
    from contextlib import chdir
    with chdir(output):
        manager.saveResult(folder='.')
    fig, ax = plt.subplots(figsize=(10, 4))
    manager.showResult(ax=ax, logScale=True, label='Resistivity (ohm m)')
    fig.savefig(output / 'model.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    np.savetxt(output / 'observed_predicted.csv',
               np.column_stack((data['rhoa'], manager.inv.response, data['err'])),
               delimiter=',', header='observed_ohm_m,predicted_ohm_m,relative_error', comments='')
    from backend_common import write_comparison_metrics
    write_comparison_metrics(output, rows, np.asarray(manager.inv.response), settings)
    (output / 'run.json').write_text(json.dumps({
        'settings': asdict(settings), 'pygimli_version': pg.__version__, 'backend': 'pygimli',
        'measurements': len(rows), 'inversion_options': settings.inversion_options(), 'chi_squared': float(manager.inv.chi2()),
        'relative_rms_percent': float(manager.inv.relrms()),
    }, indent=2), encoding='utf-8')
