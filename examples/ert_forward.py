"""Run a small ERT forward model for a homogeneous 100 ohm-m half-space."""

from importlib.metadata import version

import numpy as np
import pygimli as pg
from pygimli.physics import ert


def main():
    survey = ert.createData(elecs=np.linspace(0, 40, 11), schemeName="dd")
    mesh = pg.meshtools.createParaMesh(
        survey, paraDepth=15, paraMaxCellSize=5, quality=34
    )
    apparent_resistivity = np.asarray(
        ert.simulate(
            mesh, scheme=survey, res=100.0, noiseLevel=0,
            noiseAbs=0, returnArray=True, verbose=False
        )
    )
    if apparent_resistivity.size != survey.size() or survey.size() == 0:
        raise RuntimeError("The forward model did not return the full survey.")
    if not np.all(np.isfinite(apparent_resistivity)) or np.any(apparent_resistivity <= 0):
        raise RuntimeError("The model returned invalid apparent resistivities.")
    median = float(np.median(apparent_resistivity))
    if not np.isclose(median, 100.0, rtol=0.2):
        raise RuntimeError(f"Expected approximately 100 ohm-m, got {median:.2f}.")
    print(f"pyGIMLi {version('pygimli')}: {survey.size()} ERT measurements")
    print(f"Median apparent resistivity: {median:.2f} ohm-m (expected 100)")


if __name__ == "__main__":
    main()
