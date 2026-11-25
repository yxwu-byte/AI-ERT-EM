# Synthetic ERT sample library

All examples are deterministic synthetic **flat-surface 2D** surveys. They are
for learning and checking the workflow, not field measurements. Positions are
in metres. Assigned relative errors are 3%; no random measurement noise is added.
`tools/generate_samples.py` rebuilds the forward models with pyGIMLi 1.6.1.

- `homogeneous.csv`: a 100 ohm m half-space, Wenner alpha, 16 electrodes.
- `conductive_block.csv`: a shallow 30 ohm m target in 100 ohm m background.
- `resistive_block.csv`: a 300 ohm m target in 100 ohm m background, dipole–dipole.
- `layered.csv`: an upper 60 ohm m layer over 180 ohm m ground at 2 m depth.
- Matching `.ohm` files use the native BERT electrode/data structure.

The following files encode the **same conductive-block measurements**:

| Input | Import choices |
|---|---|
| `conductive_block.csv` | Standard format; imports directly |
| `conductive_block.ohm` | BERT; uses the supplied `err` column |
| `wenner_res2dinv.dat` | RES2DINV Wenner alpha; assign a 3% error estimate |
| `resistance_percent.tsv` | Positions in metres, measurement = resistance in ohms; errors = percent |
| `voltage_current.csv` | Semicolon-separated; positions in metres; measurement = voltage/current; voltage = mV; current = mA; errors = percent |
| `electrode_ids.csv` | Electrode IDs; select `electrodes.csv` as the id,x position table; errors = fraction |

Conversion preserves signed voltage/resistance and the A/B/M/N ordering. The
flat-half-space geometric factor converts resistance to apparent resistivity;
negative or non-finite apparent resistivity is rejected instead of silently
changing its sign. Topography, remote electrodes, IP and RES2DINV arrays other
than Wenner alpha are not supported by these native importers. Other flat arrays
can be mapped from an explicit four-electrode table.
