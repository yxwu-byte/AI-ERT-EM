"""Retain installed package license metadata in the redistributable folder."""
from importlib.metadata import distributions
from pathlib import Path
import shutil
import sys

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
for dist in distributions():
    name = dist.metadata.get('Name', 'unknown')
    target = output / f'{name}-{dist.version}'
    target.mkdir(exist_ok=True)
    for file in dist.files or ():
        parts = str(file).lower()
        if any(token in parts for token in ('license', 'copying', 'notice')) or str(file).endswith('/METADATA'):
            source = Path(dist.locate_file(file))
            if source.is_file():
                # Preserve relative paths within a package to avoid collisions.
                relative = Path(*[p for p in Path(str(file)).parts if p not in ('..', '.')])
                dest = target / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
# The frozen interpreter is part of the distribution too.
for candidate in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE'):
    if candidate.exists():
        shutil.copy2(candidate, output / 'Python-LICENSE.txt')
