"""Headless entry point used by self-contained optional engine packs."""
import json
import sys
from pathlib import Path
from runtime import configure_runtime, redirect_worker_log
from core import Settings, run_inversion


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    configure_runtime()
    # The build embeds this identifier; no module names are accepted from survey input.
    engine=json.loads((Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'engine-id.json').read_text())['engine']
    if len(sys.argv)!=3 or sys.argv[1]!='--worker':
        raise ValueError('Usage: ERTEngine --worker <run folder>')
    folder=Path(sys.argv[2]).resolve()
    stream=redirect_worker_log(folder)
    try:
        run_inversion(folder/'survey.csv',folder,Settings(**json.loads((folder/'settings.json').read_text())),backend=engine)
    except Exception:
        import traceback
        traceback.print_exc()
        return 1
    finally:
        stream.flush()
    return 0


if __name__=='__main__':
    sys.exit(main())
