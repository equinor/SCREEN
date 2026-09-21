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
- The single-reservoir design-matrix workflow is now implemented:
    - `--case-name` selects one named workbook scenario for a run.
    - `runscripts/run_workbook_scenarios_batch.py` executes all named scenarios in isolated output directories.
    - Workbook generators create named multi-scenario inputs and updated Wildcat/Smeaheia examples.
    - Each result records the selected assumptions in `scenario.json` beside the shared `well_input.json`.
    - `--plot` optionally saves a WellClass sketch and pressure QC image as `qc_plot.png`.
    - `GridPolicy` exposes explicit `reservoir_permx` and `overburden_permx` values in mD, with backward-compatible defaults for older workbooks.
    - `runscripts/validate_scenario_outputs.py` checks required outputs, logs, file sizes, and checksums.
- Optional result inspection is implemented and intentionally kept downstream of GaP:
    - `runscripts/export_wellviz_xz.py` provides a standalone Plotly XZ export.
    - `runscripts/export_wellviz_indexed.py` creates a compact Parquet-backed package with source, property, timestep, and J-column selection.
    - `runscripts/serve_wellviz_parquet.py` serves filtered slices locally.
    - The historical `src/WellViz/` Dash application is retained only as reference; it is not a supported entry point.

These helpers do not create native `.EGRID`/`.INIT` files unless an external simulator command is explicitly supplied.

## Next

environment when there is a concrete use case.
### 1. Automate scenario influence validation

Deliver a report for a batch run that compares selected quantities across
scenario directories and labels them as expected invariants or scenario-driven
outputs.

- Invariant checks: grid dimensions, LGR geometry, and static `EGRID`/`INIT`
    structure where applicable.
- Influence checks: `scenario.json`, WellClass `qc_plot.png`, and selected
    `UNRST` pressure/saturation values.
- Output: a machine-readable JSON report plus a concise CLI summary.

Done when a deliberately changed `p_fluid_contact` case is reported as
different in pressure outputs and a changed geometry/grid policy is reported
as different in the corresponding grid artifacts.

### 2. Make the input contract explicit

Add typed validation and unit declarations for `GridPolicy` and the
WellClass-to-GaP adapter, including permeability, pressure, and depth fields.
Keep legacy workbook parsing compatible through documented defaults.

Done when invalid units or missing required policy values fail before simulator
execution, and the workbook documentation lists field names, units, defaults,
and precedence.

### 3. Strengthen pure GaP regression coverage

Add a small committed `.EGRID`/`.INIT` fixture and golden CARFIN checks for one
vertical well. Cover boundary indices, material precedence, and output closure
without requiring CIRRUS or PFLOTRAN.

Done when the GaP mesh transformation can be verified in a clean Python-only
environment with deterministic artifacts.

### 4. Make salinity a shared pressure and CIRRUS input

Define one salinity contract across the WellClass pressure calculations and the
CIRRUS input deck. The implementation should:

- Allow a `PressureTable` to receive either `rho_brine` or salinity. If salinity
    is supplied, derive the brine density through the PVT model; if both are
    supplied, define and validate the precedence rather than silently mixing the
    two. The salinity unit and basis must be explicit, including the conversion
    between the pressure/PVT representation and CIRRUS concentration units.
- Propagate the selected salinity into the generated CIRRUS equilibration deck.
    The generated `SALT_TABLE` should use `CONCENTRATION_UNITS MASS` and replace
    the fixed `0.032` values in `SALTVD` with the mass concentration used by the
    pressure calculation, while retaining the generated depth interval.
- Support both a single salinity value, stretched over the required depth
    interval, and a depth-dependent salinity curve. The latter should accept
    salinity control points and interpolate or otherwise validate them according
    to the same depth-coordinate contract used by the pressure table.

Done when pressure tests prove density-only, salinity-only, and depth-varying
inputs; deck-generation tests prove the concentration units and values are
updated; and a scenario using one salinity definition produces consistent
pressure and CIRRUS salt-table inputs.

### 5. Generalize the workbook into a design matrix

Rename the user-facing `SubsurfaceAssumptions` sheet to `DesignMatrix` while
keeping a documented compatibility path for existing workbooks. Each row
should define one named simulation case and may override parameters that are
shared by the physical well description. The design matrix should support, at
minimum:

- `reservoir_permx` and `overburden_permx` from `GridPolicy`;
- casing-cement permeability;
- plug-cement permeability; and
- the existing pressure, salinity, temperature, fluid-contact, and other
    scenario assumptions.

The shared well sheets should remain the source of physical geometry, while
scenario overrides should be applied through one typed, validated merge step
with explicit units, defaults, and precedence. A selected case must produce a
self-contained resolved scenario record so batch runs are reproducible and
cannot accidentally inherit values from another case.

Done when one workbook can build multiple isolated cases from the same well,
each with independently varied grid and cement permeability values; the
resolved `scenario.json` records every effective parameter; legacy
`SubsurfaceAssumptions` workbooks remain readable; and tests verify that
changing material permeability affects the relevant outputs without changing
the shared well geometry or unrelated grid structure.

### 6. Give generated cases unique, navigable names

Keep `TEMP-*` for canonical template assets only. When a design matrix is
expanded into multiple cases, derive a unique filesystem and simulator case
stem from the workbook metadata and the scenario identity, for example a
sanitized project/well name plus the scenario name or a stable scenario index.
The naming contract should:

- be deterministic, filesystem-safe, and collision-resistant;
- preserve the human-readable scenario name where possible;
- include a stable index or identifier when names are duplicated or changed;
- apply consistently to output directories, model/deck files, generated
    includes, logs, and result exports; and
- retain the original template provenance separately from the generated case
    name.

The resolved case metadata should record the source template, workbook
metadata, scenario name, scenario index, and final case stem. Where supported
by CIRRUS, write the human-readable scenario name into the generated input
deck as well, so the file remains identifiable when viewed outside its output
directory.

Done when a workbook with ten scenarios produces ten uniquely named,
independently navigable case directories and simulator decks, with no
overwriting or ambiguous `TEMP` results; rerunning the same workbook produces
the same names; and the batch manifest plus each `scenario.json` can map every
result back to its design-matrix row and template source.

The local Parquet viewer remains sufficient for the current predefined XZ
inspection. Timestep animation, richer hover metadata, and hosted Webviz/FMU
integration remain parked until a concrete analysis need appears.

## Later

These are intentionally lower priority than the Next items:

1. **LWRES-inspired low-resolution LGR mode.** Add a named refinement policy
   using current WellClass geometry and CARFIN writers. Validate parent-cell DZ
   conservation, material precedence, simulator index conversion, and unchanged
   output from standard mode before supporting it.
2. **Multi-reservoir design policy.** Define interval selection, layer counts,
   equilibration regions, and permeability precedence before changing the
   single-reservoir contract. Done when one workbook can produce two explicitly
   separated reservoir regions with deterministic tests.
3. **GaP module relocation.** Move GaP-owned grid/LGR modules out of the
   WellClass namespace while retaining temporary re-exports. Done when imports,
   notebooks, and tests use the new location and the compatibility layer is
   documented.
4. **Wellbore-defect scenarios.** Specify casing holes, cement channels,
   microannuli, and fractures as separate scenario inputs; implement one
   representation and validate it against simulator transmissibility behavior
   before adding more defect types.

## Boundaries

These are implementation rules with concrete checks:

- `LGRBuilder` receives a validated coarse grid; test that it does not create
    `.EGRID`/`.INIT` files.
- `prepare_init_case` may write `TOPS`/`DZ` and GRDECL text, but only an
    explicit simulator command may create native `.EGRID`/`.INIT` files.
- Every depth, pressure, and permeability input has a declared unit and
    coordinate system; reject ambiguous workbook values before execution.
- Scenario output is isolated under `<output-root>/<case-name>/`; batch tests
    must verify no case writes into another case's directory.
- The existing pre-existing-grid JSON-to-LGR path remains a regression test
    while coarse-grid preparation evolves.
- Legacy scripts under `experiments/legacy/` and `originals/` may inform
    behavior but cannot become supported entry points without tests and an
    explicit ownership decision.

The scripts in `experiments/legacy/` contain historical examples of tops generation, template handling, pressure initialization, and simulator orchestration. They are references for future work, not new implementation boundaries.

Legacy CSV-oriented recipes are kept for compatibility and migration only; new projects should prefer canonical JSON inputs or the workbook adapter path.
