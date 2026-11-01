"""Explicit conversion to the common flat-surface ERT interchange format."""
import csv
import io
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from core import COLUMNS, load_csv


def geometric_factor(a, b, m, n):
    if len({a, b, m, n}) != 4:
        raise ValueError('Each measurement needs four distinct finite electrode positions.')
    denominator = 1 / abs(a-m) - 1 / abs(a-n) - 1 / abs(b-m) + 1 / abs(b-n)
    if not math.isfinite(denominator) or abs(denominator) < 1e-14:
        raise ValueError('Degenerate electrode geometry.')
    return 2 * math.pi / denominator


@dataclass
class ImportOptions:
    coordinate_mode: str = 'positions'
    position_scale: float = 1.0
    value_mode: str = 'rhoa'
    error_percent: bool = False
    default_error: float = 0.03
    voltage_scale: float = 1.0
    current_scale: float = 1.0
    electrode_file: str | None = None


def table(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    text = '\n'.join(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#'))
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t')
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    except csv.Error:
        lines = text.splitlines()
        if not lines:
            raise ValueError('The table is empty.')
        headers = lines[0].split()
        records = [dict(zip(headers, line.split(), strict=True)) for line in lines[1:]]
        return headers, records
    headers = reader.fieldnames or []
    records = list(reader)
    if not headers or not records:
        raise ValueError('A header and at least one measurement are required.')
    if len(headers) != len(set(headers)) or any(None in row for row in records):
        raise ValueError('Duplicate headers or inconsistent row lengths.')
    return headers, records


ALIASES = {
    'ax': ['ax','a_x','xa','a','c1'], 'bx': ['bx','b_x','xb','b','c2'],
    'mx': ['mx','m_x','xm','m','p1'], 'nx': ['nx','n_x','xn','n','p2'],
    'value': ['rhoa','apparent_resistivity','resistivity','rho_a','r','resistance','u','voltage','v'],
    'error': ['error','err','relative_error','error_pct','error_percent','std'],
    'current': ['i','current','current_ma','current_a'],
}


def suggest_mapping(headers):
    normalized = {h.strip().lower(): h for h in headers}
    return {key: next((normalized[a] for a in names if a in normalized), '') for key,names in ALIASES.items()}


def convert_table(path, mapping, options):
    if options.coordinate_mode not in ('positions', 'indices') or options.value_mode not in ('rhoa', 'resistance', 'voltage_current'):
        raise ValueError('Unsupported coordinate or measurement mode.')
    if not math.isfinite(options.default_error) or not 0 < options.default_error < 1:
        raise ValueError('Default error must be a fraction between 0 and 1.')
    for name in ('position_scale','voltage_scale','current_scale'):
        value = getattr(options, name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Unit scales must be finite and positive.')
    headers, records = table(path)
    required = ['ax','bx','mx','nx','value'] + (['current'] if options.value_mode == 'voltage_current' else [])
    if any(mapping.get(key) not in headers for key in required):
        raise ValueError('Map all electrode, measurement and required current columns.')
    coordinates = {}
    if options.coordinate_mode == 'indices':
        if not options.electrode_file:
            raise ValueError('Electrode-ID data require an electrode table with columns id,x (metres or selected units).')
        eheaders, electrodes = table(options.electrode_file)
        if not {'id','x'} <= set(eheaders):
            raise ValueError('Electrode table requires id,x headers.')
        for electrode in electrodes:
            identifier = float(electrode['id'])
            if not math.isfinite(identifier) or identifier != int(identifier):
                raise ValueError('Electrode IDs must be finite integers.')
            if identifier in coordinates:
                raise ValueError('Duplicate electrode ID.')
            if any(float(electrode.get(key,0) or 0) != 0 for key in ('y','z')):
                raise ValueError('Only flat, collinear surface electrodes are supported.')
            coordinates[identifier] = float(electrode['x']) * options.position_scale
    rows = []
    for line, record in enumerate(records, 2):
        try:
            raw = [float(record[mapping[key]]) for key in COLUMNS[:4]]
            if options.coordinate_mode == 'indices':
                raw = [coordinates[x] for x in raw]
            else:
                raw = [x * options.position_scale for x in raw]
            value = float(record[mapping['value']])
            if options.value_mode == 'voltage_current':
                current = float(record[mapping['current']]) * options.current_scale
                if current == 0:
                    raise ValueError('Current cannot be zero.')
                value = value * options.voltage_scale / current
            if options.value_mode != 'rhoa':
                value *= geometric_factor(*raw)
            error = float(record[mapping['error']]) if mapping.get('error') else options.default_error
            if mapping.get('error') and options.error_percent:
                error /= 100
            rows.append(dict(zip(COLUMNS, [*raw, value, error])))
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            raise ValueError(f'Line {line}: {exc}') from exc
    validate_rows(rows)
    report = {'source': str(Path(path).name), 'measurements': len(rows), 'mapping': mapping,
              'options': asdict(options), 'estimated_errors': not bool(mapping.get('error')),
              'operations': ['Mapped electrode coordinates to metres',
                             f'Converted {options.value_mode} to apparent resistivity (ohm m)',
                             'Converted errors to relative fractions; preserved all measurements']}
    return rows, report


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(rows):
    # Reuse the exact engine input checks; a spooled temporary file avoids divergent rules.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as folder:
        path = Path(folder) / 'survey.csv'
        write_csv(path, rows)
        load_csv(path)


def read_bert(path, default_error=0.03):
    lines = [line.strip() for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    cursor = 0
    count = int(lines[cursor]); cursor += 1
    coordinates_header = ['x','z']
    if lines[cursor].startswith('#'):
        coordinates_header = lines[cursor].lstrip('#').split(); cursor += 1
    positions = []
    for _ in range(count):
        values = dict(zip(coordinates_header, map(float, lines[cursor].split()), strict=True)); cursor += 1
        if any(values.get(key,0) != 0 for key in ('y','z')):
            raise ValueError('BERT input contains topography or off-line electrodes; this version supports flat 2D surveys.')
        positions.append(values['x'])
    while lines[cursor].startswith('#'):
        cursor += 1
    n_data = int(lines[cursor]); cursor += 1
    if not lines[cursor].startswith('#'):
        raise ValueError('BERT measurements require a # a b m n rhoa err header.')
    headers = lines[cursor].lstrip('#').split(); cursor += 1
    rows = []
    for line in lines[cursor:cursor+n_data]:
        record = dict(zip(headers, map(float,line.split()), strict=True))
        if record.get('valid',1) == 0:
            raise ValueError('BERT file contains invalid-marked rows. Review or remove them explicitly before import.')
        indices = [record[key] for key in ('a','b','m','n')]
        if any(i != int(i) or not 1 <= i <= len(positions) for i in indices):
            raise ValueError('BERT indices must be one-based finite electrode IDs; remote electrodes are unsupported.')
        coordinates = [positions[int(i)-1] for i in indices]
        if 'rhoa' in record:
            rhoa = record['rhoa']
        else:
            resistance = record.get('r')
            if resistance is None:
                resistance = record['u'] / record['i']
            rhoa = resistance * geometric_factor(*coordinates)
        rows.append(dict(zip(COLUMNS, [*coordinates,rhoa,record.get('err',default_error)])))
    if len(rows) != n_data:
        raise ValueError('BERT measurement count does not match its header.')
    validate_rows(rows)
    return rows, {'source': Path(path).name, 'format': 'BERT', 'measurements':len(rows),
                  'estimated_errors': 'err' not in headers, 'default_error':default_error}


def read_res2dinv_wenner(path, default_error=0.03):
    lines = [line.strip() for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if int(lines[2]) != 1:
        raise ValueError('This RES2DINV importer supports Wenner alpha (array code 1). Use the mapped CSV importer for other arrays.')
    n, position_type = int(lines[3]), int(lines[4])
    if position_type not in (0,1) or int(lines[5]) != 0:
        raise ValueError('Unsupported RES2DINV position or measurement flag (IP is unsupported).')
    rows = []
    for line in lines[6:6+n]:
        x, spacing, rhoa = map(float,line.split())
        if spacing <= 0:
            raise ValueError('Wenner spacing must be positive.')
        a = x - 1.5 * spacing if position_type == 1 else x
        rows.append(dict(zip(COLUMNS,[a,a+3*spacing,a+spacing,a+2*spacing,rhoa,default_error])))
    trailing = lines[6+n:]
    if len(rows) != n or any(float(value) != 0 for line in trailing for value in line.split()):
        raise ValueError('Measurement count mismatch or unsupported topography/trailing RES2DINV data.')
    validate_rows(rows)
    return rows, {'source':Path(path).name,'format':'RES2DINV Wenner alpha','measurements':len(rows),
                  'estimated_errors':True,'default_error':default_error}
