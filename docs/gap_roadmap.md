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
| 9 | Represent a localized casing hole | Experimental; static opening/isolation and one-year pressure-driven transfer verified |
| 10 | Generate hole-transfer reporting from the workbook | Done; verified on CIRRUS (Smeaheia, one year) |
| 11 | Align FIPLEG aquifer reporting with the current coarse-grid boundaries | Redefined 2026-10-20 (water/overburden side walls 7, bottom layer 5); new definition not yet checked on CIRRUS |
| 12 | Run only new or unfinished workbook cases | Basic version done (run only new cases, flag unverified, dry run); fingerprints, retry of killed runs, orphans open |
| 13 | Clean up the CIRRUS template deck | Partial; generated `BRINE` now matches salt tables; CIRRUS comparison and cleanup pending |

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
metadata. Open-hole permeability is part of the free-fluid definition in
`GridPolicy` (`free_fluid_permx`, `free_fluid_poro`, shared with the ocean layers).
The defaults are fixed; a `DesignMatrix` row can override them for a sensitivity.

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

### 9. Represent a localized casing hole

**Status: experimental implementation; static CIRRUS opening and isolation
verified; one-year pressure-driven transfer verified on Smeaheia.** First defect slice for
a concrete well; no general defect framework is required.

**In practice:** describe one hole using the affected casing's stable `name`
from `HoleCasings`, depth in m TVDMSL, and hole diameter in m. Preserve the
well geometry and open only the selected casing interface after generating
the standard LGR and material assignments.

**Placement assumption:** without an XY position or azimuth, use the midpoint
of the casing's `+X` side. Record this deterministic assumption with the
resolved casing, layer, affected faces, and multipliers in case metadata.
It is a modeling convention, not a measured hole location.

The implemented fields are `casing_hole_casing`,
`casing_hole_depth_mTVDMSL`, and `casing_hole_diameter_m`: all three or none,
one hole per scenario. The standalone builder accepts matching flags. Resolved
faces/areas are saved beside the include and in workbook case metadata.
Depth lookup uses absolute EGRID corners, not the internal cumulative-Z origin.
The current implementation uses only `MULTX` on +X, distributes circular area
proportionally to face overlaps with a centered diameter-wide Y span, and
rejects coincident casing interfaces and unsupported grid geometry. This
replaces the earlier experimental nearest-face filling rule.
See the [workflow guide](gap.md#experimental-localized-casing-hole) for the
controlled sealed/partial/full-open CIRRUS acceptance check.

**Real CIRRUS evidence (2026-10-09, user-reported local runs):**

- Generated Wildcat parent grid: `20 x 20 x 79`; `TEMP_LGR`:
  `22 x 22 x 430`. Zero-duration controls used explicit final `MULTX`
  assignments at one-based face `(15, 11, 47)`.
- Sealed/half/full controls exported `MULTX` values `0`, `0.5`, and `1`,
  with `TRANX` values `0`, `0.0025261160917580128`, and
  `0.0050522321835160255`. The half/full ratio was exactly `0.5`;
  only that entry changed in `MULTX` and `TRANX`, and `PERMX` was unchanged.
  This confirms positive-X indexing and replacement of the existing zero
  multiplier for this control, with exported transmissibility scaling.
- The actual `Casing 20 in` hole at `200 m TVDMSL`, diameter `0.1 m`,
  opened exactly faces `(15, 11, 47)` and `(15, 12, 47)`. Each exported
  `MULTX` was `0.012651538476347923` and `TRANX` was
  `6.391850911313668e-05`; no other LGR `MULTX` or `TRANX` entries changed.
- Parent and LGR dimensions, index frames, and cell corners were identical
  to the sealed case. Exported LGR `MULTY`, `MULTZ`, `PERMX`, `PERMY`,
  `PERMZ`, `PORO`, and `EQLNUM` were unchanged.
- Area reconstructed from exported multipliers was
  `0.007853981766232154 m2`, versus requested
  `0.007853981633974483 m2`, within the `1e-6` relative export tolerance.
  Builder allocation retains its `1e-12` relative tolerance.

These checks establish static opening and isolation for this case, not
pressure-driven leakage, a calibrated hole-flow law, or arbitrary grids.

**Smeaheia dynamic evidence (runs reported 2026-10-10; plots verified
2026-10-12, CIRRUS 1.9):**

- Both sealed and hole cases completed 365 days. Both removed mechanical
  plug `mplug2`, retained cement plug `cplug9`, and used 10 mD for
  `Cement 13 3/8 in`. The hole case opened `Casing 13 3/8 in` at
  650 m TVDMSL with diameter 0.1 m.
- The `22 x 22 x 270` LGR opening comprises positive-X faces
  `(14, 11, 130)` and `(14, 12, 130)`, each with multiplier
  `0.013923971426024894`. Test-only FIPHOL assigns their inner cells to
  region 1, outer cells to region 2, and the remaining LGR to region 3.
  The same zonation was applied to both cases.
- At both faces, initial inner/outer pressures were identical between
  cases: `78.24778747558594` / `66.01054382324219`, with gas saturations
  1 / 0. CO2 was already initialized at the hole; this test does not
  establish reservoir-to-hole migration.
- Hole `RGFR_HOL:1-2` at day 365 was `3.082140446 m3/day`; its peak
  reported magnitude was `7.547787189 m3/day`. `RGFT_HOL:1-2` reached
  `1166.561401 m3`. At gas surface density `1.871 kg/m3`, these correspond
  to about `5.76668 kg/day` final rate, `14.12191 kg/day` peak, and
  `2182.63638 kg` cumulative direct transfer.
- The sealed case omitted the 1-2 pair but exported 1-3 and 2-3.
  CIRRUS 1.9 source revision `00028b774` registers pair summaries from its
  connection map, not from nonzero flow: connected zero-flow pairs remain
  exported. The sealed 1-2 curve is therefore labelled inferred zero, not
  an exported measurement.
- User-supplied rate and total plots verified the mass-unit labels and
  dashed inferred-zero sealed curve. The FIPLEG 1-6 ocean gas-rate plot
  showed no visible transfer for either case over the year; exact numerical
  ocean-rate values were not supplied.

These results support dynamic direct hole connectivity for this setup, not
ocean arrival or a calibrated physical hole-flow law. FIPHOL is now generated
from the workbook (item 10).

**Smeaheia 100-year cement sweep (runs reported 2026-10-20; end totals only):**

- Setup: the Smeaheia workbook with `mplug2` removed (test only), `Casing 13 3/8 in`
  opened at 650 m TVDMSL, `overburden_permx = 0` in `GridPolicy`, and
  `Cement 13 3/8 in` permeability set per `DesignMatrix` row. All 11 cases
  reached 2125-01-01 and passed `validate_scenario_outputs.py`. The sealed
  control (5000 mD cement, 0.2 m, `casing_hole_open=FALSE`) has no `1-2` pair
  and an exactly zero `2-3` total.
- `RGFT_HOL:1-2` at 100 years, in kg using the case's gas surface density:

| Cement perm (mD) | 0.2 m hole | 0.05 m hole |
| --- | --- | --- |
| 0.0005 | 3 | not run |
| 5 | 15,206 | not run |
| 50 | 371,232 | 370,603 |
| 200 | 1,947,466 | 1,943,622 |
| 500 | 4,761,288 | 4,752,087 |
| 1,600 | 12,345,627 | not run |
| 5,000 | 23,857,467 | not run |

- A 16x larger opening area changed the total by 0.17-0.20% at the three
  permeabilities run with both sizes: cement permeability, not hole area, set
  the transfer. This agrees with the one-year runs above.
- Transfer per mD of cement permeability rises from about 3,000 kg (5 mD) to a
  maximum near 9,700 kg (200 mD), then falls to about 4,800 kg (5000 mD). The
  5 to 50 mD step is superlinear (24x for 10x) and the 1600 to 5000 mD step is
  sublinear (1.9x for 3.1x). What limits the high end was not determined.
- Not established: the rate history (plots were not reviewed), ocean or
  overburden arrival (`FIPLEG` pairs were not examined), and any case with a
  permeable overburden. These totals do not give a calibrated hole-flow law.
- The `compare_scenario_outputs.py` report initially failed every case on
  "grid geometry changed". The cause was the comparison counting generated
  hole blocks as geometry, not a grid change; it ignores those blocks now.

**Area-equivalent opening:**

- Locate the depth layer and the selected casing's sealed interface. Define
  deterministic ownership at layer boundaries; reject depths outside that
  casing and non-positive or non-finite diameters.
- The circular opening area is `A = pi * (diameter / 2)^2`. For an X-normal
  face use `A_face = DY * DZ`; for a Y-normal face use `DX * DZ`, not
  `DX * DY`. A partially opened face receives `MULTX` or `MULTY` equal to
  its allocated opening area divided by its face area.
- Center a lateral span equal to the diameter at the side midpoint.
  Allocate circular area proportionally to each face's positive span overlap,
  even when a single tall, narrow face has enough area to hold the hole.
  A midpoint at a face boundary shares the opening; output uses increasing J.
  Keep all faces on the same +X casing side and K layer. Do not spread in Z,
  cross into another casing, or rebuild the grid. Reject a span extending
  beyond the side, excessive total area, or any per-face allocation above
  capacity rather than clipping or moving area outside the span.
- Keep each multiplier in `[0, 1]` and conserve total allocated area:
  `sum(multiplier * face_area) = A` within a declared numerical tolerance.
  Leave all other casing faces sealed and existing material properties
  unchanged. This represents equivalent open area, not a resolved circular
  hole shape when multiple faces are used.

**Done when:** reuse the existing LGR/CARFIN writers with a small final
face-override step; tests cover sub-face, exact-face, multi-face, invalid
input, and unchanged no-defect output. Verify CIRRUS face indexing and
keyword ordering so the opening replaces the existing zero casing multiplier
rather than being multiplied by zero or overwritten later. A real CIRRUS
baseline/defect run must confirm unchanged geometry and intended connectivity;
the area ratio is a screening approximation, not a calibrated orifice-flow
law.

### 10. Generate hole-transfer reporting from the workbook

**Status: done; verified on a CIRRUS host (2026-10-17).** Any casing-hole
location now also generates `FIPHOL` inside the LGR (`write_hole_reporting`).
`casing_hole_open=FALSE` (CLI `--casing-hole-report-only`) gives a sealed
control with the same location and reporting cells but no opening. Resolved
cells and an `opened` flag are saved in `resolved_casing_hole`. Because the
zonation is generated, regeneration keeps it. Rows without a hole location
produce no `FIPHOL`.

**CIRRUS evidence (Smeaheia, one-year runs, user-reported):**

- A workbook-only batch of `nohole`, an open 0.2 m hole and a sealed 0.2 m
  hole (Casing 13 3/8 in, 650 m TVDMSL) succeeded. `nohole` has no `FIPHOL`;
  the open and sealed LGRs have identical `FIPHOL` lines (9: one background
  line plus two per face; four faces at `i=14`, `k=130`, `j=10-13`, 0.05 m
  overlap each). Only the open LGR contains the opening; its allocated area
  matches the requested `pi * 0.1^2`.
- Open cases export `RGFT_HOL:1-2`, `1-3` and `2-3`. The sealed case exports no
  `1-2` pair and its `2-3` total is zero, as in the earlier CIRRUS 1.9
  behaviour. Region 1-2 and 2-3 totals agree within 0.4%.
- At 365 days, `RGFT_HOL:1-2` was 752.4 m3 (0.1 m hole, 100 mD cement), 750.4 m3
  (0.2 m hole, same cement), 27.9 m3 (0.1 m, 10 mD cement) and 1226.0 m3
  (0.1 m, 10 mD cement, permeable overburden). The last is about 5% above the
  earlier manual-FIPHOL Smeaheia result (1166.56 m3); that run's overburden
  and other settings were not re-checked, so this is agreement, not
  reproduction.
- Hole area was not the limiting factor in these setups: doubling the
  diameter changed the transfer by 0.3%, while cement and overburden
  permeability changed it by factors of 27 and 44. Do not read a hole-size
  sensitivity from the tight-overburden cases.

Not checked: CIRRUS partition-count limits beyond the three regions used.

**In practice:** prepare and queue a complete scenario batch from one workbook,
including hole-transfer reporting, without editing the generated decks.

- Define explicit reporting-location inputs independent of whether a casing
  opening is enabled. Sealed controls must be able to use the same reporting
  cells as hole cases; do not infer pairings from scenario names.
- Reuse resolved interface geometry to label the inner adjacent cells as
  FIPHOL 1, outer adjacent cells as 2, and remaining LGR cells as 3. Include
  every face in the diameter span, not only its midpoint.
- Generate the zonation inside CARFIN before ENDFIN, before a final local or
  queued run. Wire workbook, standalone, and batch workflows consistently.
- Preserve FIPLEG and other partitions, grid geometry, properties, and casing
  multipliers. Reporting must not itself create an opening.
- Record reporting regions and resolved cells in case metadata, validate
  partition limits supported by CIRRUS, and leave no-reporting output unchanged.

**Done when:** a workbook-only paired batch produces matching FIPHOL cells
in sealed/open cases, survives regeneration, and exports usable region-pair
summaries on CIRRUS. Tests cover multi-face openings, explicit sealed reporting,
invalid locations, and unchanged cases without reporting.

### 11. Align FIPLEG aquifer reporting with the current coarse-grid boundaries

**Status: redefined 2026-10-20 and implemented; the new definition has not been
checked on CIRRUS.** Outdated definition
reported by the user (2026-10-12): FIPLEG 5 was intended to identify aquifer
cells with multiplied pore volume. The aquifer representation moved to the
outer edges of the coarse grid, but region 5 stayed on the bottom
`aquifer_layers` of the reservoir.

**Decision (2026-10-20, replaces the 2026-10-17 one):** the aquifer pore volume
moves from all outer columns to where it can only provide water and pressure
support. Three independent multipliers, each settable in `GridPolicy` and per
`DesignMatrix` row: `water_overburden_wall_porv_multiplier` (four side walls of
the water and overburden layers), `reservoir_bottom_porv_multiplier` (the whole
bottom reservoir layer) and `reservoir_wall_porv_multiplier` (default 1). The
first two default to the legacy `porv_multiplier` (2000). Multiplied reservoir
side walls gave CO2 an almost unlimited sink or source, which is not realistic,
so the third multiplier, default 1, covers them above the bottom layer.
`FIPLEG` follows the multiplied cells: 7 for the water and overburden
side walls (regions 1 and 2 shrink to their interior columns), 5 for the bottom
reservoir layer, and no new region for the reservoir walls, which stay in 3.
`aquifer_layers` and `aquifer_permx` are unchanged. The wall boxes for `FIPLEG 7`
and `PORV` come from one shared list in `prepare_init_case.py`. The wellbore
cells (region 6: pipe, open hole and casing-cement boxes) sit in
a central parent cell (10, 10 in the default 20 x 20 grid), away from the edge
columns; other grid sizes were not checked. Earlier cases are not comparable
region-for-region or in pressure response. Open point: whether the reservoir
walls need their own region.

- Trace current boundary-aquifer placement and pore-volume multipliers, then
  compare them with FIPLEG 5 assignments in generated parent and LGR outputs.
- Define region 5 ownership at coarse-grid edges and parent/LGR interfaces,
  including precedence against reservoir, overburden, and ocean labels.
- Update generation and directly related region descriptions together.
  Preserve physical aquifer properties and boundary behavior; this is a
  reporting correction, not an aquifer-model redesign.
- Preserve other region identifiers where possible and explicitly document
  changed memberships so old and regenerated summary results are not silently
  treated as equivalent.

**Done when:** regression checks establish that region 5 identifies the
intended current aquifer cells, with no unintended changes to other regions
or physical properties, and CIRRUS INIT/summary checks confirm the corrected
zonation and aquifer-related transfer interpretation.

**CIRRUS evidence for the superseded 2026-10-17 definition (region 5 on the outer
reservoir columns; user-reported, 2026-10-20):** the global `FIPLEG` array of a
case generated after the change, read from its `.INIT`, on a `20 x 20 x 63` grid
(7 water, 16 overburden, 40 reservoir layers): region 1 had 2800 cells
(`k 1-7`), region 2 had 6400 (`k 8-23`), region 3 had 12960 (`i, j 2-19`,
`k 24-63`) and region 5 had 3040. Region 5 was exactly the 76 outer columns of
the grid in layers 24-63, and the four regions add up to all 25200 cells with no
overlap and no remaining region 4. Not checked: the second (LGR) `FIPLEG` array
in the same `.INIT`, other grid sizes, and any summary or transfer vector that
uses region 5.

### 12. Run only new or unfinished workbook cases

**Status: basic version implemented (2026-10-20); the rest is open.**
Requested by the user (2026-10-12). Before this, the batch runner processed every
workbook scenario, so after adding rows there was no safe way to start only the
new ones.

**Implemented** in `run_workbook_scenarios_batch.py`, using only files already in
each case folder and no scheduler, so it works with or without LSF. Only cases
without a folder are run. For an existing folder, `model/<stem>.LOG` ending with
`Run completed` means finished (skipped); anything else is listed as unverified
(not run) for the user to check, since the run may be live, killed or crashed.
`--dry-run` prints the plan. A finished case whose `DesignMatrix` values differ
from its saved `scenario.json` gets a warning. The manifest marks skipped cases
`existing` or `unverified`; `--force` keeps its old meaning (rerun everything).
Not done: a fingerprint covering `GridPolicy`, the well sheets and run options;
automatic retry of killed runs; orphaned case folders; merging per-case history
(job id, queue, timings) into the manifest.

**In practice:** add rows to a workbook, ask which cases are new, changed,
queued, running, finished, or failed, then prepare and submit only the cases
that need it.

- Add a status/dry-run mode that compares workbook scenarios with the output
  root and prints the planned action per case without changing files.
- Derive state from evidence, not directory existence: generated inputs,
  initialization output, LGR include, queue submission record/job ID, final
  summary/restart files, and whether the final run reached the requested end
  date.
- Store a fingerprint of each case's resolved inputs (workbook values, template,
  simulation years, casing hole, and reporting options). A case whose inputs
  changed is reported as stale and is not silently skipped or overwritten.
- Add an incremental mode that runs missing cases and, when explicitly
  requested, failed or stale ones. Never resubmit a queued or running job, and
  never delete existing output; changed cases need explicit confirmation or a
  new output root.
- Merge per-case records into the manifest instead of replacing earlier
  results, including failure messages, submission time, queue, CPU count, and
  job ID. Report cases removed from the workbook as orphaned, not deleted.

**Done when:** after adding cases to a completed batch, a dry run lists only
the new cases as pending; the incremental run prepares and queues only those
cases; and tests cover new, finished, failed, queued/running, stale, orphaned,
and partially generated cases without overwriting existing output.

### 13. Clean up the CIRRUS template deck

**Status: partial; salinity generation corrected (2026-10-16); broader cleanup
and CIRRUS comparison pending.** Reviewed against the CIRRUS 1.9 source
(2026-10-13). The workflows default to
`test_data/examples/wildcat-pflotran/model/TEMP-0.in`.
`parameterize_cirrus_deck` rewrites dates, both equilibration datums, the
`RTEMPVD` and `SALTVD` tables, global `BRINE`, and removes the commented wells
section. Everything else is copied unchanged. That untouched remainder
includes legacy keywords and stale comments that make it hard to tell which
values matter.

**In practice:** a user reading a generated deck can tell which values come
from the workbook and which are fixed template choices, and both salinity
settings in the deck agree.

- **Salinity mismatch (generation fixed; CIRRUS comparison pending).** CIRRUS requires a global `BRINE` whenever
  `SALTVD` is used; cell salinity comes from the salt tables, while `BRINE`
  converts water to surface volumes and is used by wells and analytical
  aquifers. The workflow writes the workbook salinity to the salt tables as a
  mass fraction but previously left `BRINE 0.032 MOLE` unchanged: 0.032 mass
  fraction is 0.57 mol/kg, 0.032 mole fraction is 1.84 mol/kg. The shared deck
  writer now generates `BRINE <salinity> MASS` from the same workbook value
  for initialization and final runs, and rejects missing or duplicate global
  declarations. Regression tests cover matching tables, fresh water,
  non-default salinities, and repeated configuration. Measure the effect on
  water summary volumes in a separate run; existing cases stay unchanged.
- **Redundant or legacy keywords.** `RESERVOIR_DEFAULTS` is already the default
  for the `GAS_WATER` mode and CIRRUS logs it as a legacy keyword.
  `WRITE_MASS_RATES` appears in both output blocks; confirm whether each is
  needed. `SUMMARY_D` is empty, and `NEWTON_SOLVER` sets `RTOL`/`ITOL` to
  `1.0D-20`, which effectively disables them; keep them only with a comment
  that says so.
- **Isothermal inputs.** The run is `ISOTHERMAL`, so the energy equation is
  off. Confirm in the source whether `SPECIFIC_HEAT` and the thermal
  conductivities have any effect, then remove or label them.
- **Stale comments.** Remove the "symmetrical cold injection" title, the old
  pressure-datum notes, the incorrect `BRINE ... PPM` comment, and the
  "Perm region 1 / SATNUM 1" labels on `ch2`. Keep `ch2`: the generated LGR
  assigns `SATNUM 2` to pipe and open-hole cells for linear relative
  permeability; label it as such.
- **Template sprawl.** Four `TEMP-0.in` variants have drifted (inline vs
  external temperature table, active injector, `FINAL_DATE 2525`), and the
  default folder is named `wildcat-pflotran` but holds the CIRRUS template.
  It also carries `ALPHA.in`, `.backup`, `.copy`, `.preview.inc`,
  `temperature_gradient.inc`, and a ResInsight project that staging never
  copies. Establish one clearly named canonical template folder separate
  from example/reference cases, and point all preparation, single-case, and
  batch workflow defaults to it. Keep reference decks with their associated
  simulation outputs, explicitly labelled as fixtures rather than maintained
  templates. Check references before removing genuinely unused copies, and
  preserve `--template-root` for intentional custom templates.
- Mark the workflow-owned values in the template (for example
  `! generated from workbook`) so users don't edit lines that get overwritten.

**Done when:** a generated deck has matching `BRINE` and salt-table salinity;
every remaining keyword is either generated, deliberately fixed and
commented, or removed; the template asset hashes in
`tests/gap/test_template_assets.py` are updated; and a cleaned deck
reproduces an existing CIRRUS run, apart from documented `BRINE` effects.

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
4. **Additional wellbore-defect scenarios.** Casing holes are the first
   concrete slice (Next item 9). Cement channels, microannuli, and fractures
   remain deferred; choose a concrete use case and validate its representation
   against simulator transmissibility behavior before adding another type.
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
