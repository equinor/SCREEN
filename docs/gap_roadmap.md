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
- The single-reservoir workbook-to-CIRRUS-to-LGR path is complete for the current supported contract. It parameterizes the coarse GRDECL, preserves required CIRRUS assets, creates `.EGRID`/`.INIT`, generates the case LGR include (`<case_stem>_LGR.grdecl`), and prepares the same deck for the final run.
- Smeaheia validation completed on a CIRRUS-enabled Linux host, before case naming was introduced: the 10-year run used `FINAL_DATE 1 JAN 2035` and produced `.EGRID`, `.INIT`, and `TEMP_LGR.grdecl`. The generated deck used `DATUM_D = WGC_D = 1282.5 m` and `PRESSURE = 129.99 Bar`.
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

Each item starts with its status and an **In practice** note: what changes for
someone running the workflow, in terms of what they can do or what goes wrong
less often. The technical detail follows for whoever picks the item up.

| # | Item | Status |
| --- | --- | --- |
| 1 | Compare scenario outputs automatically | Done; first real-CIRRUS check pending (item 7) |
| 2 | Make the input contract explicit | Done |
| 3 | Strengthen pure GaP regression coverage | Partly done |
| 4 | Share scalar salinity between pressure and CIRRUS | Done |
| 5 | Generalize the workbook into a design matrix | Case-wide overrides done; per-interval overrides open |
| 6 | Give generated cases unique, navigable names | Done; real-CIRRUS check pending (item 7) |
| 7 | Confirm recent changes on a CIRRUS host | Open (reminder) |

### 1. Compare scenario outputs automatically

**Status: done** in `runscripts/compare_scenario_outputs.py`, tested with
synthetic simulator data. Not yet run on a real CIRRUS batch (see item 7).

**In practice:** after a batch run, one command tells you, for every case
against a baseline case, what was changed in the inputs and what changed in the
results:

```bash
uv run python runscripts/compare_scenario_outputs.py --output-root work/results
```

It catches two mistakes that are easy to miss by eye:

- a sensitivity that silently had no effect (the input changed, but pressure
    and saturation came out identical); and
- a "physics" sensitivity that accidentally changed the grid, so the cases can
    no longer be compared cell by cell.

**Details:** the report lists changed `scenario.json` and `grid_policy.json`
fields, checks grid dimensions, cell corners and LGR geometry for invariance,
compares static `INIT` properties (such as `PERMX`, `PORO`, `EQLNUM`), and
compares `UNRST` pressure and saturation per timestep. Changes to
geometry-affecting `GridPolicy` fields are flagged as a separate grid
sensitivity study. Output is a JSON report plus a short CLI summary.

### 2. Make the input contract explicit

**Status: done.**

**In practice:** unit and value mistakes in the workbook stop the run when the
workbook is read, with a clear message, instead of producing a CIRRUS case with
wrong numbers. Examples: `depth_unit=ft`, `permeability_unit=D`, a zero target
layer thickness, a negative permeability, or a missing permeability for a
cement interval. The accepted field names, units and defaults are listed in the
[workflow guide](gap.md).

**Details:** `GridPolicy` (`src/WellClass/libs/utils/xlsx_parser.py`) and
`SimulationScenario` (`src/GaP/libs/models/simulation_scenario.py`) are typed
models with declared units (depths in m TVDMSL, pressures in bar, permeabilities
in mD, salinity as mass fraction). `WellDataFrame` rejects non-mD, missing,
negative or non-finite permeabilities before LGR generation. Older workbooks
without unit fields default to these units.

### 3. Strengthen pure GaP regression coverage

**Status: partly done.**

**In practice:** this is about being able to change the GaP code (the step that
turns the well description into refined LGR cells) and find out in a normal
`pytest` run, without CIRRUS, whether the generated LGR file changed. Today a
change that shifts a cement interval by one cell, or changes which material wins
where two intervals overlap, can pass the tests unless it happens to hit one of
the few lines that are checked exactly.

**Done so far:** committed `.EGRID`/`.INIT` fixtures (Wildcat `TEMP-0`, Smeaheia
`TEMP-0` and `GEN_NOLGR_PH2`) and `tests/well_class/test_json_to_lgr.py`, which
checks coarse and refined dimensions, exact CARFIN bounds, finite non-negative
permeabilities, the closing `ENDFIN`, and three exact Wildcat property lines.

**Remaining:**

- a golden-file test: compare one complete generated LGR file with a committed
    reference, so any change shows up as a reviewable diff;
- an explicit material-precedence test where open hole, cement bond and plug
    intervals overlap; and
- a closure check that every refined cell receives the expected properties.

Done when these run in a clean Python-only environment with deterministic
artifacts.

### 4. Share scalar salinity between pressure and CIRRUS

**Status: complete for scalar salinity.**

**In practice:** the brine density behind the SCREEN pressure plots and the
salt concentration written into the CIRRUS deck now come from the same workbook
value, so the pressure QC plot and the simulation can no longer silently assume
different brines.

**Details:** the canonical input is a NaCl mass
fraction of total solution mass, default `0.032`. `PressureTable` accepts either
that salinity or an explicit `rho_brine`; supplying both is rejected. The PVT
model derives reference brine density from the selected salinity, and generated
CIRRUS salt tables use `CONCENTRATION_UNITS MASS` with the same value over the
generated depth interval. The old template's `MOLE` label is not a conversion
contract; the canonical value is interpreted directly as mass fraction.

Regression tests cover density-only and salinity-driven pressure, invalid
inputs, and an end-to-end non-default scalar shared by pressure and deck output.
Depth-varying salinity profiles are not currently supported and are deferred
until a concrete modeling use case requires them.

### 5. Generalize the workbook into a design matrix

**Status: initial case-wide sensitivity support is implemented.**

**In practice:** one workbook can define several cases on the same well, each
with its own reservoir or overburden permeability and its own cement or plug
permeability, and the batch runs them all. The limitation today is that a
cement or plug permeability override applies to *every* cement or plug
interval in the well at once; you cannot yet say "only the second plug is
degraded".

**Details:** new workbooks
use `DesignMatrix`; legacy `SubsurfaceAssumptions` sheets remain readable. Each
row defines a named case sharing the same physical well. Rows can override
`reservoir_permx` and `overburden_permx` in mD, plus case-wide `cb_perm` and
`barrier_perm` values for all casing-cement or plug intervals. Empty overrides
fall back to the grid policy, the individual well record where present, then
CLI defaults as documented. Effective permeability values are saved with case
metadata. Open-hole permeability remains a fixed high-permeability default and
is deliberately not a scenario sensitivity.

**Follow-up work:** let a cement override target one interval, identified by a
stable row ID from the `HoleCasings` or `Plugs` sheet, with `ALL` keeping the
current case-wide behavior. Rename abbreviated workbook fields (for example
`cb_perm`) to names that state the material, property and unit, keeping the old
names as aliases for existing workbooks. Tests should show that a targeted
override changes only its interval, while geometry and other intervals stay the
same.

### 6. Give generated cases unique, navigable names

**Status: done** (PR #134). Confirmation on a real CIRRUS host is pending
(item 7).

**In practice:** generated cases are no longer all called `TEMP-0`. A deck,
grid include, result file or log found on disk is named after its well and case
(for example `model/wildcat_hot_case.in`), and its first line says which
workbook row and template it came from. Batch results go into one directory per
case, and `batch_manifest.json` maps every `DesignMatrix` row to its directory
and whether it succeeded. Rerunning the same workbook gives the same names, so
new results replace the matching old ones instead of landing somewhere else.

**Details:** the case stem is `<well>_<case_name>`, from the workbook
`Metadata` name (or wellbore identifier) and the `DesignMatrix` case name,
sanitized to letters, digits and `_`. Duplicate `case_name` values are
rejected; names that only collide after sanitizing or by letter case get the
1-based row index appended. The stem names the case directory, deck,
coarse-grid and LGR includes, simulator outputs and logs, and the deck starts
with a `# SCREEN case:` comment. `scenario.json` records the stem, row index,
workbook and template provenance under `case_metadata`. Validation, comparison
and WellViz export find case files through `scenario.json`, falling back to
`TEMP-*` names for older outputs. `TEMP-*` is now reserved for the canonical
template assets. The rules live in `src/GaP/libs/case_naming.py`.

**Remaining:** the LGR name written inside generated LGR files is still
`TEMP_LGR` (`--lgr-name`). It is visible to the simulator, so renaming it waits
for the CIRRUS check in item 7.

### 7. Confirm recent changes on a CIRRUS host

**Status: open (reminder).**

**In practice:** the automated tests use a fake simulator that only copies
fixture grid files next to the deck. They prove SCREEN writes and finds the
right files, but not that CIRRUS itself accepts the new case names. Until this
check is done, the first real batch after PR #134 could fail or produce results
under unexpected names.

On a Linux host with CIRRUS, run a short two-case batch and the two checking
scripts:

```bash
uv run python runscripts/run_workbook_scenarios_batch.py \
    --xlsx test_data/examples/wildcat/wildcat_workbook.xlsx \
    --output-root work/cirrus_check \
    --sim-command "runcirrus -i -nm 6 {deck}" \
    --simulation-years 1 --run-final --force
uv run python runscripts/validate_scenario_outputs.py --output-root work/cirrus_check
uv run python runscripts/compare_scenario_outputs.py --output-root work/cirrus_check
```

Check that:

- CIRRUS accepts a deck whose first line is the `# SCREEN case:` comment (no
    parse error in `logs/<case_stem>_initialization.log`);
- CIRRUS names its outputs after the deck (`model/<case_stem>.EGRID`, `.INIT`,
    `.UNRST`). If it does not, the wrapper stops with "did not produce both
    .EGRID and .INIT";
- the final run picks up `include/<case_stem>_LGR.grdecl`;
- validation passes, and the comparison reports identical grid geometry with
    different pressure results between the two cases (the first real-data run
    of item 1); and
- whether CIRRUS limits LGR name length (for example to 8 characters), before
    `TEMP_LGR` is renamed.

Done when the checks pass and the date, host and CIRRUS version are noted here.

## Later

These are intentionally lower priority than the Next items:

1. **LWRES-inspired low-resolution LGR mode.** *In practice:* a coarser,
   faster refinement option for quick screening or large batches, trading
   detail near the well for run time. Add a named refinement policy
   using current WellClass geometry and CARFIN writers. Validate parent-cell DZ
   conservation, material precedence, simulator index conversion, and unchanged
   output from standard mode before supporting it.
2. **Multi-reservoir design policy.** *In practice:* model a well that crosses
   two storage or pressure units (for example a reservoir plus a deeper
   aquifer) with separate pressure regions; today a workbook supports one
   reservoir. Define interval selection, layer counts,
   equilibration regions, and permeability precedence before changing the
   single-reservoir contract. Done when one workbook can produce two explicitly
   separated reservoir regions with deterministic tests.
3. **GaP module relocation.** *In practice:* no change in results; the grid and
   LGR code moves from the WellClass package to the GaP package, so it is
   obvious which package owns what. Old imports keep working for a while.
   Move GaP-owned grid/LGR modules out of the
   WellClass namespace while retaining temporary re-exports. Done when imports,
   notebooks, and tests use the new location and the compatibility layer is
   documented.
4. **Wellbore-defect scenarios.** *In practice:* describe a specific failure,
   such as a casing hole at a given depth or a channel through the cement,
   instead of only lowering the permeability of whole cement intervals.
   Specify casing holes, cement channels,
   microannuli, and fractures as separate scenario inputs; implement one
   representation and validate it against simulator transmissibility behavior
   before adding more defect types.
5. **Richer result viewing.** *In practice:* animate results over time or
   browse them in a hosted dashboard. The local Parquet viewer covers the
   current cross-section inspection; timestep animation, richer hover
   metadata, and hosted Webviz/FMU integration stay parked until a concrete
   analysis need appears.

## Boundaries

These are implementation rules with concrete checks:

- `LGRBuilder` receives a validated coarse grid; test that it does not create
    `.EGRID`/`.INIT` files.
- `prepare_init_case` may write `TOPS`/`DZ` and GRDECL text, but only an
    explicit simulator command may create native `.EGRID`/`.INIT` files.
- Every depth, pressure, and permeability input has a declared unit and
    coordinate system; reject ambiguous workbook values before execution.
- Scenario output is isolated under `<output-root>/<case_stem>/`; batch tests
    must verify no case writes into another case's directory.
- The existing pre-existing-grid JSON-to-LGR path remains a regression test
    while coarse-grid preparation evolves.
- Legacy scripts under `experiments/legacy/` and `originals/` may inform
    behavior but cannot become supported entry points without tests and an
    explicit ownership decision.

The scripts in `experiments/legacy/` contain historical examples of tops generation, template handling, pressure initialization, and simulator orchestration. They are references for future work, not new implementation boundaries.

Legacy CSV-oriented recipes are kept for compatibility and migration only; new projects should prefer canonical JSON inputs or the workbook adapter path.
