# Experiment Scripts

The supported product path is documented through the five canonical notebooks:

1. `notebooks/01_wellclass.ipynb` demonstrates WellClass input, geometry, pressure/PVT, and plots.
2. `notebooks/02_gap_grid.ipynb` demonstrates GaP grid refinement and material assignment.
3. `notebooks/03_wellclass_to_gap.ipynb` demonstrates canonical JSON through LGR GRDECL generation.
4. `notebooks/04_init_case_preprocessing.ipynb` demonstrates parameterized initialization-case preparation.
5. `notebooks/05_workbook_to_cirrus_lgr.ipynb` demonstrates selecting Wildcat or Smeaheia and following the workbook-to-CIRRUS-to-LGR workflow.

The maintained command-line workflow is in `runscripts/`. Use `runscripts/run_workbook_to_cirrus_lgr.py` for the complete workbook-to-CIRRUS-to-LGR path. The scripts in this directory are optional utilities and historical recipes, not a second supported workflow API.

| Script | Purpose | Prerequisites | Status |
| --- | --- | --- | --- |
| `gap_wellclass.py` | Convert a canonical well JSON and an existing `.EGRID`/`.INIT` case into an LGR GRDECL. | `resdata` and committed grid files; no simulator required. | Supported CLI |
| `gap_pflotran.py` | Run PFLOTRAN to create coarse/LGR grid data, then build an LGR GRDECL. | `runpflotran1.8`, simulator input files, and legacy YAML/CSV input. | Experimental; prefer the `runscripts/` wrapper |
| `well_sketch.py` | Produce a standalone well construction sketch. | Legacy YAML/CSV input. | Legacy utility; not canonical |
| `well_sketch_pressure.py` | Produce a well sketch with pressure curves. | Legacy pressure input and PVT database. | Legacy utility; not canonical |
| `legacy/screen_workflow.py` | Copy a simulator template, derive tops, run coarse and LGR simulator cases, and plot results. | External `runpflotran1.8`; legacy Well API and hard-coded template assumptions. | Legacy research recipe |
| `legacy/screen_well_to_gap.py` | Assemble a CIRRUS/PFLOTRAN case with pressure initialization, grid generation, and LGR output. | External `runcirrus`; hard-coded paths and simulator template layout. | Legacy research recipe |

## Legacy Research Recipes

The two scripts under `legacy/` are retained as design references. They contain useful ideas for simulator orchestration, pressure initialization, template handling, and future coarse-grid generation, but they are not supported entry points. For new work, use the workbook wrapper in `runscripts/` or notebook 05; use notebook 3 when an existing `.EGRID`/`.INIT` pair is already available.

## Quick Checks

Check CLI availability without running a simulator:

```bash
python -m experiments.gap_wellclass --help
python -m experiments.gap_pflotran --help
```

Run the maintained workbook workflow from the repository root:

```bash
python runscripts/run_workbook_to_cirrus_lgr.py \
    --xlsx test_data/examples/wildcat/wildcat_workbook.xlsx \
    --output-root /tmp/wildcat-case \
    --sim-command "runcirrus -i -nm 6 {deck}"
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