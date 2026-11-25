# Build on Windows with Python 3.12, from the repository root.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata, collect_delvewheel_libs_directory

root = Path(SPECPATH).parent
binaries, datas, hiddenimports = [], [], ['backend_pygimli']
for package in ('pygimli', 'pgcore'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden
# Preserve the Windows solver DLL directory expected by the wheel's loader.
datas, binaries = collect_delvewheel_libs_directory('pgcore', datas=datas, binaries=binaries)
for distribution in ('pygimli', 'pgcore', 'scooby'):
    datas += copy_metadata(distribution)
datas += [(str(root / 'examples'), 'examples')]
datas += [(str(root / 'packaging' / 'THIRD_PARTY_NOTICES.txt'), '.')]
datas += [(str(path), '.') for path in (root / 'packaging').glob('Qt-*.txt')]
# Include the Qt LGPL text that ships with the binding, when available.
datas += collect_data_files('PySide6', includes=['**/*LICENSE*', '**/*license*'])
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=['simpeg', 'PyHydroGeophysX', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtQml', 'PySide6.QtQuick', 'IPython', 'jupyterlab'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ERTStudio',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ERTStudio')
