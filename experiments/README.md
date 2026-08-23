# Experiment Scripts

The supported product path is documented and tested through the three canonical notebooks:

1. `notebooks/01_wellclass.ipynb` demonstrates WellClass input, geometry, pressure/PVT, and plots.
2. `notebooks/02_gap_grid.ipynb` demonstrates GaP grid refinement and material assignment.
3. `notebooks/03_wellclass_to_gap.ipynb` demonstrates canonical JSON through LGR GRDECL generation.

The scripts in this directory are optional command-line utilities, not a second workflow API.

| Script | Purpose | Prerequisites | Status |
| --- | --- | --- | --- |
| `gap_wellclass.py` | Convert a canonical well JSON and an existing `.EGRID`/`.INIT` case into an LGR GRDECL. | `resdata` and committed grid files; no simulator required. | Supported CLI |
| `gap_pflotran.py` | Run PFLOTRAN to create coarse/LGR grid data, then build an LGR GRDECL. | `runpflotran1.8`, simulator input files, and legacy YAML/CSV input. | Experimental |
| `well_sketch.py` | Produce a standalone well construction sketch. | Legacy YAML/CSV input. | Legacy utility; not canonical |
| `well_sketch_pressure.py` | Produce a well sketch with pressure curves. | Legacy pressure input and PVT database. | Legacy utility; not canonical |
| `legacy/screen_workflow.py` | Copy a simulator template, derive tops, run coarse and LGR simulator cases, and plot results. | External `runpflotran1.8`; legacy Well API and hard-coded template assumptions. | Legacy research recipe |
| `legacy/screen_well_to_gap.py` | Assemble a CIRRUS/PFLOTRAN case with pressure initialization, grid generation, and LGR output. | External `runcirrus`; hard-coded paths and simulator template layout. | Legacy research recipe |

## Legacy Research Recipes

The two scripts under `legacy/` are retained as design references. They contain useful ideas for simulator orchestration, pressure initialization, template handling, and future coarse-grid generation, but they are not supported entry points. Use `gap_pflotran.py` for current simulator experiments and notebook 3 for the tested JSON-to-GaP workflow.

## Quick Checks

Check CLI availability without running a simulator:

```bash
python -m experiments.gap_wellclass --help
python -m experiments.gap_pflotran --help
```

Run the supported existing-grid conversion:

```bash
python -m experiments.gap_wellclass \
    --sim-path ./test_data/examples/wildcat \
    --well wildcat.json \
    --sim-case TEMP-0 \
    --output-dir ./experiments/output
```

The simulator-dependent command is intentionally not part of the pure-Python test suite.