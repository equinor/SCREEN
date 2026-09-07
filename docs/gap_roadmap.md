# GaP Roadmap

This document tracks implementation work for the GaP path. The architectural contract is defined by the [SCREEN Architecture Manifesto](architecture_manifesto.md); this roadmap does not redefine it.

## Current State

The supported GaP path is:

```text
canonical well JSON + existing .EGRID/.INIT
    -> WellProcessed
    -> WellDataFrame
    -> LGRBuilder
    -> CARFIN/LGR GRDECL
```

The current `LGRBuilder` assumes that a suitable coarse grid already exists. This remains the regression path and must stay stable while coarse-grid preparation is developed upstream.

Completed coarse-grid preparation slices:

- `CoarseGridSpec` makes vertical domain and layer-count assumptions explicit.
- `CoarseGridEnvelope` derives vertical coverage and reference-point lateral bounds from processed wells. GaP treats wells as vertical for coarse-grid sizing; WellClass retains deviation for TVDMSL conversion.
- `build_vertical_grid_schedule` creates water, overburden, and reservoir `DZ` values.
- Well top/bottom coverage and invalid depth ordering are validated.
- `format_vertical_grid_recipe` and `write_vertical_grid_recipe` produce a simulator-oriented `TOPS`/`DZ` text recipe.
- Notebook 2 demonstrates the recipe against the Wildcat JSON fixture.
- A standalone preprocessing notebook demonstrates recipe generation and dry-run case staging:
    - `notebooks/04_init_case_preprocessing.ipynb`
- A workbook-driven adapter path stages init cases from a multi-sheet user input deck:
    - `runscripts/prepare_init_case_from_xlsx.py`
    - `src/WellClass/libs/utils/xlsx_parser.py`
    - `runscripts/create_well_input_workbook.py`
- Template assets now have explicit integrity checks in CI-focused tests:
    - `tests/gap/test_template_assets.py`
- A CLI bridge now converts WellClass JSON plus an existing `.EGRID`/`.INIT` case into LGR/CARFIN output:
    - `runscripts/build_lgr_from_json.py`
    - `tests/gap/test_build_lgr_from_json.py`
- The wrapper now orchestrates workbook staging, CIRRUS initialization, `.EGRID`/`.INIT` validation, LGR generation, and final-deck configuration:
    - `runscripts/run_workbook_to_cirrus_lgr.py`
- Staged grids derive two equilibration regions from layer counts: `EQLNUM 1` for water/overburden and `EQLNUM 2` for reservoir layers.
- The two CIRRUS equilibration blocks share generated temperature and salt tables. The overburden datum uses WellClass hydrostatic pressure; the `CO2_column` datum and gas-water contact use the workbook fluid-contact pair.
- Ready-to-edit workbook examples are included for Wildcat and Smeaheia, including optional survey sheets:
    - `test_data/examples/wildcat/wildcat_workbook.xlsx`
    - `test_data/examples/smeaheia/smeaheia_workbook.xlsx`
- The single-reservoir workbook-to-CIRRUS-to-LGR path is complete for the current supported contract. It parameterizes the coarse GRDECL, preserves required CIRRUS assets, creates `.EGRID`/`.INIT`, generates `TEMP_LGR.grdecl`, and prepares the same deck for the final run.
- Smeaheia validation completed on a CIRRUS-enabled Linux host: the 10-year run used `FINAL_DATE 1 JAN 2035` and produced `.EGRID`, `.INIT`, and `TEMP_LGR.grdecl`. The generated deck used `DATUM_D = WGC_D = 1282.5 m` and `PRESSURE = 129.99 Bar`.
- Notebook 3 supports an optional generated-grid mode: it can consume a completed workbook-wrapper output directory while fixture mode remains deterministic for CI.
- The complete workbook wrapper has simulator-free dry-run coverage: a fake CIRRUS executable supplies a valid coarse `.EGRID`/`.INIT` pair, then the test verifies LGR creation, final-deck configuration, and both captured logs.
- A pure-Python coverage report compares a required `CoarseGridEnvelope` with explicit grid bounds, reports directional missing margins, and summarizes optional cell sizes:
    - `src/WellClass/libs/grid_utils/coverage.py`
    - `tests/gap/test_grid_coverage.py`
- `CirrusBackend` makes executable availability, resolved commands, phase logs, exit codes, and initialization outputs explicit for the workbook wrapper:
    - `src/GaP/libs/cirrus_backend.py`
    - `tests/gap/test_cirrus_backend.py`

These helpers do not create native `.EGRID`/`.INIT` files unless an external simulator command is explicitly supplied.

## Next

The single-reservoir workflow is complete for the current contract. The next changes require separate scenario-policy design rather than incremental plumbing.

## Later

- Adapt or extend coarse cells when the well envelope is not covered.
- Preserve existing properties when adapting a grid.
- Support separate PFLOTRAN and CIRRUS input/output backends.
- Add a small committed synthetic grid for pure-Python tests.
- Replace hard-coded permeability and cell-size assumptions with modeled configuration.
- Design a first-class **design matrix** for one physical wellbore. A `DesignMatrix` workbook sheet should use one named case per row and common columns for potentially variable parameters. For example, a 20-column table can hold `case_name` plus 19 parameters such as initial/contact pressure, casing-hole geometry, cement permeability, grid policy, or salinity. Ten rows must produce ten separate reproducible simulation cases, each with its own parameterized deck/GRDECL, LGR output, logs, and results. Define precedence as: item-specific well override -> selected design-matrix value -> documented default.
    - WellClass pressure scenarios currently support multiple calculation/plotting cases, but the workbook staging path selects only the first `SubsurfaceAssumptions` row. A selected scenario must instead propagate its pressure/contact values into CIRRUS `EQUILIBRATION` cards and its physical-property assumptions into CARFIN/GRDECL generation.
    - Keep the physical well description shared and immutable across scenarios. Scenario selections must not rewrite the canonical well JSON; they should produce isolated output directories such as `<output-root>/<scenario-name>/`.
    - Start with single-reservoir scenario variants. Interval-aware/multi-reservoir selection remains a separate later design.
- Design interval-aware and multi-reservoir policies only after the single-reservoir contract is stable; they are explicitly out of scope for the current milestone.
- Migrate GaP-owned grid and LGR modules from `src/WellClass/libs/grid_utils/` into `src/GaP/libs/`, keeping `WellDataFrame` as an explicit compatibility adapter until callers have migrated. Preserve temporary re-exports so the tested workflow remains stable during the move.
- Model explicit wellbore-defect scenarios as simulation inputs separate from the physical well description. The workbook should describe casing holes (default or explicit diameter) and cement defects: channel/hole diameter, fracture opening, or microannulus geometry. WellClass should display these scenarios in sketches without changing the base well geometry. GaP/CARFIN should own their grid-property representation:
    - casing holes: a localized transmissibility variation replacing the default zero casing transmissibility, with a geometric area-based multiplier considered as a candidate model;
    - cement channels/holes, microannuli, and fractures: use literature-backed relationships to derive an effective permeability from the channel diameter, microannulus size, or fracture opening. This approach may combine low-permeability cement with a high-permeability defect contribution and assign the resulting effective value to the full cement-plug region;
    - cement channels/holes: alternatively represent the defect explicitly as a high-permeability column of grid cells within the cement-plug region while retaining the cement permeability elsewhere. When the channel cross-sectional area is smaller than the cell `DX * DY` area, derive the cell porosity, vertical transmissibility, and permeability consistently from the sub-cell geometry.
    Validate each defect representation against CIRRUS transmissibility conventions and literature before treating the proposed relationships as supported physics.

## Boundaries

- Do not put coarse-grid creation inside `LGRBuilder`; it should receive a validated coarse grid.
- Keep simulator execution optional and explicit.
- Keep `TOPS`/`DZ` text generation separate from native EGRID/INIT generation.
- Keep units, depth coordinates, margins, and target cell sizes explicit.
- Preserve the existing pre-existing-grid workflow as a regression path.

The scripts in `experiments/legacy/` contain historical examples of tops generation, template handling, pressure initialization, and simulator orchestration. They are references for future work, not new implementation boundaries.

Legacy CSV-oriented recipes are kept for compatibility and migration only; new projects should prefer canonical JSON inputs or the workbook adapter path.
