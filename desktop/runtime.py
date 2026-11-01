"""Writable runtime paths and logging for a windowed executable."""
import os
import sys
from pathlib import Path


def configure_runtime():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.cache')) / 'ERTStudio'
    base.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(base / 'matplotlib'))
    os.environ.setdefault('XDG_CONFIG_HOME', str(base / 'config'))
    os.environ.setdefault('XDG_CACHE_HOME', str(base / 'cache'))
    os.environ.setdefault('BERT_NUM_THREADS', '1')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    return base


def redirect_worker_log(folder):
    stream = (folder / 'solver.log').open('w', encoding='utf-8', buffering=1)
    sys.stdout = sys.stderr = stream
    # Native solver libraries write to C standard descriptors too.
    for descriptor in (1, 2):
        try:
            os.dup2(stream.fileno(), descriptor)
        except OSError:
            pass
    return stream


def resource_path(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / name
