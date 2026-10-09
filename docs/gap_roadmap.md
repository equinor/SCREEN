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
| 1 | Compare scenario outputs automatically | Done; verified on a real CIRRUS batch (item 7) |
| 2 | Make the input contract explicit | Done |
| 3 | Strengthen pure GaP regression coverage | Done for current Wildcat and Smeaheia regression cases |
| 4 | Share scalar salinity between pressure and CIRRUS | Done |
| 5 | Generalize the workbook into a design matrix | Case-wide and per-interval permeability overrides done |
| 6 | Give generated cases unique, navigable names | Done; verified on a real CIRRUS host (item 7) |
| 7 | Confirm recent changes on a CIRRUS host | Done for current case/LGR naming |
| 8 | Give user-facing names a clear meaning | Open |

### 1. Compare scenario outputs automatically

**Status: done** in `runscripts/compare_scenario_outputs.py`. Tested with
synthetic simulator data and verified on a real CIRRUS batch (see item 7).

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

**Status: done for the current Wildcat and Smeaheia regression cases.** Coverage
uses existing committed `.EGRID`/`.INIT` fixtures; no duplicate grid fixtures
were added.

**In practice:** a change that moves a refined boundary, changes the CARFIN
output, or alters which material is assigned to a cell now fails in a regular
Python-only test run. The failure points to a small reviewable reference file,
without requiring CIRRUS or PFLOTRAN.

**Coverage:** `tests/well_class/test_json_to_lgr.py` checks coarse/refined
dimensions, exact CARFIN bounds, non-negative finite permeability, and
`ENDFIN`. It compares the complete Wildcat LGR against
`tests/gap/fixtures/wildcat_TEMP-0_LGR.grdecl` (8.4 KB), and checks the exact
permeability ranges of both plug intervals in the two Smeaheia grid variants.
`tests/gap/test_grid_materials.py` checks that a plug replaces open-hole
material at its depth while adjacent casing-cement cells keep cement material,
and that every synthetic refined cell has the expected finite properties.

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

**Status: case-wide and per-interval permeability overrides are implemented;
per-interval overrides verified on CIRRUS.**

**In practice:** one workbook can define several cases on the same well, each
with its own reservoir or overburden permeability and its own cement or plug
permeability, and the batch runs them all. `cb_perm` and `barrier_perm` can
apply case-wide or target one named interval using `cb_perm_interval` or
`barrier_perm_interval`. `ALL` keeps the case-wide behavior.

**Details:** new workbooks
use `DesignMatrix`; legacy `SubsurfaceAssumptions` sheets remain readable. Each
row defines a named case sharing the same physical well. Rows can override
`reservoir_permx` and `overburden_permx` in mD, plus `cb_perm` and `barrier_perm`
values. The companion interval columns select by the `name` in the
`HoleCasings` or `Plugs` sheet; `ALL` applies the value to every interval of
that type. For a named target, only that interval changes. Other intervals
retain their workbook permeability where present, then use CLI defaults.
Effective permeability values and interval targets are saved with case
metadata. Open-hole permeability remains a fixed high-permeability default and
is deliberately not a scenario sensitivity.

**Per-interval overrides:** `cb_perm_interval` and `barrier_perm_interval`
select an interval by its `name` in the `HoleCasings` or `Plugs` sheet;
`ALL` preserves the case-wide behavior. Tests verify that targeted permeability
changes affect only the selected interval and leave geometry and other
intervals unchanged. Clearer names for the override fields (such as `cb_perm`)
are covered by item 8.

**CIRRUS verification (results reported October 9, 2026):** a Wildcat workbook
contained an unchanged `baseline` and an otherwise identical
`interval_override_check` case targeting `Cement 20 in` at `0.2 mD` and
`cplug3` at `0.3 mD`. Outputs were written under
`work/cirrus_interval_override_check`.

- `validate_scenario_outputs.py` reported `OK` for both `wildcat_baseline`
  and `wildcat_interval_override_check`.
- `compare_scenario_outputs.py` reported
  `OK: wildcat_interval_override_check vs wildcat_baseline`. Grid dimensions,
  cell corners, and LGR geometry matched, and at least one compared dynamic
  pressure/saturation output differed.
- Changed scenario fields were `barrier_perm`, `barrier_perm_interval`,
  `cb_perm`, `cb_perm_interval`, and `effective_permeability_mD`. No
  `GridPolicy` fields or compared `INIT` properties changed.

This confirms simulator acceptance and a changed simulation response without
changing geometry. Isolation of non-target interval permeabilities is covered
by regression tests, not independently established by this comparison summary.

### 6. Give generated cases unique, navigable names

**Status: done** (PR #134), including confirmation on a real CIRRUS host
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

**Remaining:** the LGR name written inside generated LGR files remains
`TEMP_LGR` (`--lgr-name`). A 15-character alternative (`SCREEN_TEST_LGR`) was
accepted by CIRRUS; the maximum supported CARFIN name length is unknown and
does not need to be established unless the production default is to be renamed.

### 7. Confirm recent changes on a CIRRUS host

**Status: done for current case and LGR naming.** CIRRUS version recorded;
`SCREEN_TEST_LGR` (15 characters) passed. The maximum identifier length remains
unknown and is not needed while the production default remains `TEMP_LGR`.

**In practice:** a real two-case Wildcat batch completed through the LSF
`bigmem` queue. CIRRUS accepted the case-stem deck names, generated the expected
case-named files, and the final runs produced results that SCREEN could
validate and compare. The LSF wait in `CirrusBackend` was exercised by this run.

`CirrusBackend` polls `bjobs -a -noheader -o stat <job_id>` every 15 seconds by
default and allows up to 24 hours. Override those limits with
`--queue-poll-interval` and `--queue-timeout` (seconds) on the single-case or
batch command. Non-LSF commands that block until completion are unchanged.

The verified command was:

```bash
uv run python runscripts/run_workbook_scenarios_batch.py \
    --xlsx test_data/examples/wildcat/wildcat_workbook.xlsx \
    --output-root work/cirrus_check_lsfwait \
    --sim-command "runcirrus -q bigmem8 -nm 5 -nn 2 {deck}" \
    --simulation-years 1 --run-final --queue-poll-interval 15 \
    --queue-timeout 86400 --jobs 2
uv run python runscripts/validate_scenario_outputs.py \
    --output-root work/cirrus_check_lsfwait
uv run python runscripts/compare_scenario_outputs.py \
    --output-root work/cirrus_check_lsfwait \
    --baseline wildcat_baseline \
    --report work/cirrus_check_lsfwait/comparison.json
```

Observed results:

- LSF jobs completed successfully; the sample `bjobs -l` output showed status
    `DONE`.
- `validate_scenario_outputs.py` reported `OK` for `wildcat_baseline` and
    `wildcat_hot_case`.
- `compare_scenario_outputs.py` reported `OK: wildcat_hot_case vs
    wildcat_baseline`: grid geometry matched, no `GridPolicy` fields or `INIT`
    properties changed, and pressure/saturation outputs differed for the
    changed scenario inputs.
- Case-named `.EGRID`, `.INIT`, and `.UNRST` files were produced for both cases.

The LSF output identified submit host `st-lintgx0003` and execution hosts
`st-rsv15-15-09` and `st-rsv15-15-02`. CIRRUS reported `Cirrus SV3 2.0.7`,
compiled August 4, 2026; the `runcirrus` wrapper resolved to `/global/bin/runcirrus`.

An additional final run used `--lgr-name SCREEN_TEST_LGR` (15 characters).
LSF job `366202` finished `DONE`, the final log recorded the same status, and
`model/wildcat_baseline.UNRST` was written at 13:04 on 2026-10-06 (42,315,536
bytes). This confirms CIRRUS accepted that longer CARFIN identifier.

The maximum supported CARFIN name length was not tested. Revisit this only if
the simulator-visible default `TEMP_LGR` is to be renamed.

### 8. Give user-facing names a clear meaning

**Status: open.**

**In practice:** someone new to SCREEN, or returning after a break, should be
able to fill in a workbook or run a script without decoding abbreviations.
Today names such as `cb_perm` (casing-cement permeability), `oh_perm` (open-hole
permeability), `z_resrv`/`p_resrv` (reservoir depth and pressure) or
`--ali-way` (a legacy refinement mode named after a person) only make sense if
you already know the code. Clear names also make `scenario.json` and the
comparison reports readable on their own.

Work in order of how often people see the name:

1. **Workbook fields and command-line flags.** These are what users type. Give
    each a name that states the material, property and unit, for example
    `cb_perm` -> `casing_cement_permeability_mD`, and describe what a flag does
    rather than who wrote it. Keep the old names working as aliases with a
    deprecation warning, so existing workbooks and scripts do not break.
2. **Output files** (`scenario.json`, `grid_policy.json`, reports), which people
    read when checking results. Older outputs must still be readable by the
    validation and comparison scripts.
3. **Internal code** (for example `pt_df`, `hs_p`, `sf_depth_msl`,
    `LGR_NAME`). Rename only when that code is being changed anyway, since these
    renames carry the most risk for the least benefit to users.

#### Name Proposal for Review

These are proposals, not adopted API names. Please agree on the vocabulary
before implementation. Workbook aliases would keep existing workbooks working;
CLI aliases would keep existing scripts working. Units are written in the
proposed name where they help distinguish otherwise ambiguous values.

| Surface | Current name | Proposed name | Meaning | Unit |
| --- | --- | --- | --- | --- |
| DesignMatrix | `case_name` | `scenario_name` | Human-readable name for one assumptions row | none |
| DesignMatrix | `temperature_gradient` | `geothermal_gradient_degC_per_km` | Temperature increase with depth | degC/km |
| DesignMatrix | `ground_temperature` | `ground_temperature_degC` | Temperature at ground/seafloor | degC |
| DesignMatrix | `z_fluid_contact` | `fluid_contact_depth_mTVDMSL` | Fluid-contact depth | m TVDMSL |
| DesignMatrix | `p_fluid_contact` | `fluid_contact_pressure_bar` | Pressure at fluid-contact depth | bar |
| DesignMatrix | `z_resrv` | `reservoir_depth_mTVDMSL` | Reservoir reference depth; legacy alias | m TVDMSL |
| DesignMatrix | `p_resrv` | `reservoir_pressure_bar` | Pressure at reservoir reference depth; legacy alias | bar |
| DesignMatrix | `overburden_datum_depth` | `overburden_datum_mTVDMSL` | Depth where overburden pressure is specified | m TVDMSL |
| DesignMatrix | `salinity` | `salinity_mass_fraction` | NaCl mass divided by total solution mass | kg/kg (dimensionless) |
| GridPolicy | `reservoir_permx` | `reservoir_permeability_mD` | Reservoir horizontal permeability | mD |
| GridPolicy | `overburden_permx` | `overburden_permeability_mD` | Overburden horizontal permeability | mD |
| GridPolicy | `aquifer_permx` | `aquifer_permeability_mD` | Aquifer horizontal permeability | mD |
| GridPolicy | `target_dz_water` | `target_cell_dz_water_m` | Target vertical cell thickness in water | m |
| GridPolicy | `target_dz_overburden` | `target_cell_dz_overburden_m` | Target vertical cell thickness in overburden | m |
| GridPolicy | `target_dz_reservoir` | `target_cell_dz_reservoir_m` | Target vertical cell thickness in reservoir | m |
| DesignMatrix | `cb_perm` | `cement_sheeth_permeability_mD` | Case-wide casing-cement permeability override | mD |
| DesignMatrix | `barrier_perm` | `cement_plug_permeability_mD` | Case-wide plug/barrier permeability override | mD |
| CLI | `--sim-command` | `--cirrus-command` | Command template containing `{deck}` | none |
| CLI | `--case-name` | `--scenario-name` | Select the workbook assumptions row to run | none |
| CLI | `--oh-perm` | `--open-hole-permeability-md` | Default permeability assigned to open-hole cells | mD |
| CLI | `--cb-perm` | `--cement-sheeth-permeability-md` | Default permeability assigned to casing-cement cells | mD |
| CLI | `--barrier-perm` | `--cement-plug-permeability-md` | Default permeability assigned to plug/barrier cells | mD |
| CLI | `--ali-way` | `--legacy-depth-refinement` | Alternate refinement: uses coarse-grid reference depth, alternative lateral sizing, and a fixed 0.05 m minimum cell size | none |

Potentially overlapping depth/pressure pairs (`fluid_contact_*` and
`reservoir_*`) should stay separate: the former defines the fluid-contact
boundary, while the latter is a compatibility input used when no fluid-contact
pair is supplied. This distinction needs to remain explicit in any rename.

Done when the names are agreed, steps 1 and 2 are implemented, workbook
documentation uses the new names, and tests show that a workbook using the old
names still produces the same case.

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
