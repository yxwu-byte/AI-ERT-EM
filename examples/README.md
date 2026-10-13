# ERT example datasets

Small electrical resistivity tomography (ERT) datasets from [ResIPy](https://github.com/hkexgroup/resipy), covering three common input formats.

| Folder | Data | Measurements | Geometry | ResIPy format |
| --- | --- | ---: | --- | --- |
| `syscal_2d/` | `syscal.csv` | 344 | 24 electrode positions; coordinates included in the CSV | `Syscal` |
| `wenner_2d/` | `res2dinv-wenner32.dat` | 1,648 | Wenner array; measurement positions and spacings included | `Res2DInv` |
| `protocol_3d/` | `protocol.dat` + `elec.csv` | 644 | 75 electrodes on three parallel lines | `ProtocolDC` |

The existing [ert_forward.py](ert_forward.py) generates a separate synthetic dataset using pyGIMLi.

## Format notes

- **Syscal:** `Spa.1` through `Spa.4` describe the four electrode positions. `Rho` contains apparent resistivity, and the export also includes voltage, current, deviation, and IP fields. Preserve the leading empty CSV column and original headers when importing.
- **RES2DINV Wenner:** the six-line header identifies the survey, electrode spacing, array type, measurement count, position convention, and IP flag. Each measurement contains position, spacing, and apparent resistivity. Four trailing zero lines are retained.
- **3D protocol:** the first line gives the measurement count. Each row contains an index, four (string, electrode) pairs for A/B/M/N, and transfer resistance in ohms. Match these pairs to the `label` column in `elec.csv`; coordinates are in metres. Signed resistance values are intentional. The upstream header reports 2% added noise and removal of low/high geometric-factor measurements.

These are example inputs, not labeled inversion results or a curated machine-learning benchmark. The original files do not establish field provenance for every dataset.

## Sources and license

Source repository: **hkexgroup/resipy**  
Pinned upstream commit: `c7a281bb4cb03e7eb614e91b59bb88af66fa8d29`

- [Syscal source](https://github.com/hkexgroup/resipy/blob/c7a281bb4cb03e7eb614e91b59bb88af66fa8d29/src/examples/dc-2d/syscal.csv)
- [Wenner source](https://github.com/hkexgroup/resipy/blob/c7a281bb4cb03e7eb614e91b59bb88af66fa8d29/src/examples/parser/res2dinv-wenner32.dat)
- [3D protocol source](https://github.com/hkexgroup/resipy/blob/c7a281bb4cb03e7eb614e91b59bb88af66fa8d29/src/examples/dc-3d/protocol.dat)
- [3D electrodes source](https://github.com/hkexgroup/resipy/blob/c7a281bb4cb03e7eb614e91b59bb88af66fa8d29/src/examples/dc-3d/elec.csv)

The copied files retain ResIPy's upstream GNU GPL version 3 license; see [LICENSE-ResIPy.txt](LICENSE-ResIPy.txt). This notice applies to these imported examples. Only line endings have been normalized to LF; values and headers are unchanged.

Please cite ResIPy when using it:
Blanchy G., Saneiyan S., Boyd J., McLachlan P. and Binley A. (2020).
“ResIPy, an Intuitive Open Source Software for Complex Geoelectrical Inversion/Modeling.”
Computers & Geosciences, 137, 104423.
https://doi.org/10.1016/j.cageo.2020.104423

## Validation

Verified measurement counts, numeric fields, consistent CSV row widths, and every 3D electrode reference. Full inversion has not been run.
