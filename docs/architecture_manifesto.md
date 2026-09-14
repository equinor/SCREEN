# SCREEN Architecture Manifesto

## Purpose

SCREEN should make one workflow dependable:

> validate a well description, derive its geometry and pressure inputs, translate that information into GaP mesh primitives, and produce a reviewable grid artifact.

The immediate goal is not to modernize every module. It is to make that workflow explicit, testable, and honest about which external tools it needs.

## Document Roles

This manifesto is the architectural source of truth. It defines what SCREEN is supposed to do, which modules own each responsibility, which boundaries are stable, and which limitations are intentional.

The focused roadmaps, such as [`gap_roadmap.md`](gap_roadmap.md), are execution trackers. They record implementation status and the next concrete tasks needed to move toward this architecture; they must not redefine the ownership boundaries or canonical workflow described here. When a roadmap item conflicts with this manifesto, the manifesto takes precedence and the roadmap should be revised.

The simulator-facing file pipeline (`TEMP-0.in` -> `TEMP_GRD.grdecl` -> `tops_dz.inc` -> initialization run -> `.EGRID`/`.INIT` -> CARFIN include) is documented in [`gap.md`](gap.md). Treat that pipeline as operational guidance for reproducible runs and template governance.

The five canonical notebooks are executable explanations of the architecture:

- Optional simulator-result inspection through the maintained Plotly/Parquet WellViz-style exporters:
  - `runscripts/export_wellviz_xz.py` creates a standalone interactive XZ HTML view.
  - `runscripts/export_wellviz_indexed.py` creates a compact indexed Parquet package.
  - `runscripts/serve_wellviz_parquet.py` serves filtered property, timestep, and J-column data locally.

Deprecated or historical (kept as references, not recommended as entry points):

- Scripts under `experiments/legacy/`.
- `_originals` assets and historical notebooks not listed above.
- `src/WellViz/` historical Dash/Plotly application code; its vector-reading ideas informed the maintained exporters, but it is not part of the supported runtime.
- Legacy CSV-style input recipes for new projects; keep only for backward compatibility and migration.

The result-visualization layer is intentionally optional and downstream of the
GaP workflow. It consumes completed `.EGRID`, `.INIT`, and `.UNRST` outputs but
does not define grid generation, simulator execution, or the WellClass/GaP
ownership boundary. Further viewer features are parked until the core GaP
contracts require them.

These are important smoke paths, not yet a complete production guarantee.

## The Main Risks

### 1. The tested surface is much smaller than the implementation

The current source coverage is approximately 24%: 2,702 statements, 2,064 missed. Most of the following have no meaningful tests:

- WellClass pressure modules: `pressure.py`, `co2_pressure.py`, `pressure_scenario.py`, `barrier_pressure.py`, `pressure_table.py`.
- WellClass plotting modules.
- Most LGR mesh construction: `grid_refine_base.py`, `LGR_bbox.py`, `LGR_grid_info.py`, `LGR2GaP.py`.
- Most CARFIN writers.
- CSV parsing and parts of YAML/model validation.
- Plug and barrier derivation.

Passing tests currently prove input loading, a few bounding-box helpers, and the new adapter contract. They do not prove the complete simulation workflow.

### 2. The public API is split between two generations

The branch has a typed, list-based `WellProcessed` model, while older notebooks and scripts still use the pandas-era constructor and names. This creates failures such as old parser imports resolving to modules and `Well(...)` receiving removed arguments.

The remedy is not more compatibility aliases everywhere. Choose one canonical API, document the adapter, migrate the three canonical workflows, and then quarantine or remove old recipes deliberately.

### 3. External runtime dependencies are implicit

Python dependencies are declared in `pyproject.toml`, but several workflows also require tools and artifacts that are not Python packages:

- `runcirrus`
- `runpflotran1.8`
- simulator-generated `.EGRID`, `.INIT`, and restart files
- Eclipse/ECL tooling used by historical scripts
- `ecl` imports in legacy GaP notebooks/scripts

`resdata` is the current Python reader for grid files. The old `ecl`-based scripts should not be treated as supported entry points until they are isolated, documented, or removed.

### 4. Input semantics are not yet fully explicit

Permeability values are required at the WellClass-to-GaP boundary, but the new schema and fixtures do not consistently carry them. The adapter currently accepts explicit `oh_perm`, `cb_perm`, and `barrier_perm` values and fails when they are absent. That is better than silently inventing physics, but the long-term owner of these assumptions should be a modeled configuration object.

Other semantic questions need a written contract:

- Which depth coordinate does each GaP function consume: RKB, MSL, or TVD MSL?
- Are intervals closed, half-open, or allowed to touch at boundaries?
- What should happen when a well extends beyond the grid?
- What is the unit of permeability and pressure at each boundary?
- Are casing cement intervals matched by diameter, name, or explicit identifier?

The physical vocabulary above is part of the input contract. Every interval should also make its coordinate system, units, and role explicit. A name such as `top_tvd_msl` should not be silently interchanged with `top_rkb`, and a mesh material label should not be used as if it were a physical input type.

### 5. File and package structure obscures the supported product

`src/PressCalc`, `src/WellViz`, `src/_originals`, historical GaP scripts, root experiments, and many notebooks coexist with the current code. This makes it hard to know what should be imported, tested, or supported.

The repository needs a support classification before cleanup:

- **Supported**: WellClass models/processing, the GaP mesh path, the five canonical notebooks, and selected CLI workflows.
- **Experimental**: pressure development, plotting prototypes, simulator orchestration.
- **Historical**: `_originals`, old `ecl` scripts, removed standalone applications, superseded notebooks.

## Recommended Plan

### Phase 0: Establish the truth (small, high value)

1. Keep the five canonical notebooks as the only workflow recipes.
2. Add a short support/dependency matrix to the documentation.
3. Add a CI smoke job that runs:
   - all Python tests;
   - the WellClass notebook;
   - the GaP notebook against committed grid fixtures;
   - the end-to-end notebook and checks that a GRDECL file is written.
4. Make test output distinguish pure-Python tests from simulator-required tests.
5. Record the exact Python version and `uv.lock` environment in CI.

**Exit criterion:** a fresh environment can say, automatically, which part of the workflow works and which external tool is missing.

**Status:** substantially complete. The canonical notebook CI smoke workflow exists and runs with `uv.lock`; simulator dependency reporting and dry-run behavior remain.

### Phase 1: Lock down the WellClass contract

1. Add parameterized vertical wells: no casing, one casing, multiple casing overlaps, cement gaps, plugs, and no survey.
2. Add one deviated-well fixture with expected MD-to-TVD values.
3. Test unit conversion from feet to meters.
4. Test invalid intervals and invalid Pydantic values.
5. Test `WellProcessed` output schemas and numeric tolerances.
6. Move permeability and other modeling assumptions into an explicit configuration model.

**Exit criterion:** WellClass can be trusted independently of GaP and produces documented, stable records.

**Status:** core geometry, unit, validation, plug, pressure, and PVT contracts are covered. Remaining work is broader deviated-well and pressure/PVT scenario coverage plus explicit modeling assumptions.

### Phase 2: Test GaP as a pure transformation

1. Unit-test bounding boxes and interval-to-grid-index conversion at top, bottom, and boundary depths.
2. Test LGR size calculations with small synthetic grids.
3. Test material assignment for open hole, annulus, cement, and barrier cells.
4. Test CARFIN writers as text transformations: key sections, indices, dimensions, and output closure.
5. Use a tiny committed `.EGRID`/`.INIT` fixture for one integration test.
6. Remove or fix the current mutable-dataframe behavior in mesh builders after tests characterize it.

**Exit criterion:** GaP can prove that a known dataframe and grid produce a known mesh artifact without running PFLOTRAN/Cirrus.

**Status:** substantially complete for current bounding-box, material, CARFIN, and end-to-end smoke paths. A smaller committed grid fixture and broader material edge cases remain.

### Phase 3: Make the boundary intentional

1. Rename `WellDataFrame` to a clearly transitional adapter or move it into a GaP input module.
2. Define a typed GaP input record instead of passing loosely specified DataFrames everywhere.
3. Migrate GaP functions from legacy `drilling_df` terminology to `holes_df` or typed hole records.
4. Keep conversion to pandas at the last possible boundary, if pandas remains useful.
5. Add one end-to-end test comparing the current and refactored vertical-well geometry.

**Exit criterion:** WellClass does not know GaP’s historical dataframe vocabulary, and GaP has one documented input contract.

**Status:** in progress. Canonical aliases and internal `holes_df`/`barrier_regions_df` names exist, but legacy aliases and dataframe contracts are still present.

### Phase 4: Clarify operational workflows

1. Separate pure file generation from simulator execution.
2. Replace `os.system` with a small subprocess runner that checks executable availability, return codes, and captured logs.
3. Put simulator-dependent commands behind explicit CLI options or markers.
4. Make output directories temporary by default and avoid mutating input fixtures.
5. Add a dry-run mode that validates paths and writes planned commands without executing them.

**Exit criterion:** a user can run a dry run anywhere and a full run only when the simulator prerequisites are installed.

### Backlog: WellClass pressure scenario engine

WellClass should stay a single object a user can: (1) build well geometry from for both plotting and GaP input, (2) compute brine and CO2 pressure profiles under different scenario definitions, and (3) retrieve key pressure values at specific depths for reporting or later simulation input. Part 1 is done (`WellProcessed`).

Parts 2/3 are now implemented as a collections-based (no pandas) engine. `Pressure` owns one or more named `PressureTable` objects (well-level background curves: temperature, hydrostatic pressure, Shmin) and one or more named `PressureScenario` objects. Scenarios use their selected table while retaining their own `brine_pressure`/`fluid_pressure` arrays and resolved metadata: `z_fluid_datum`/`p_fluid_datum`, `z_store`/`p_store`, `p_delta`, and `z_MSAD`/`p_MSAD`.

The supported scenario anchors are:

1. Fluid datum only, or fluid datum plus an explicit datum pressure or `p_delta`.
2. A shallower store pressure pair, which anchors integration and derives the datum pressure at a supplied datum depth.
3. `z_MSAD`, where `p_MSAD = Shmin(z_MSAD)` anchors integration; an optional `z_store` queries the resulting fluid pressure, and can become the datum when no datum is supplied.

`PressureScenario.display_curves()` keeps complete calculated arrays available while returning full-depth brine plus the display-only fluid segment from MSAD to datum, with exact interpolated endpoints. `Pressure` may be constructed from a WellClass header or from explicit ground elevation, total depth, and RKB reference values.

Remaining/deferred:

1. A `get_values_at_depth(depth)`-style accessor on `PressureScenario` (mirroring `PressureTable.get_values_at_depth`) so specific brine/CO2 pressure values can be pulled out without re-deriving the whole profile.
2. Explicitly deferred: phase-envelope/fluid-composition-aware variable-density PVT (multiple mixtures, bubble/dew-point detection, brine salinity correction) — keep the current single-fluid (`"co2"`) variable-density integration until there is a concrete need.
3. `barrier_pressure.py`'s `compute_barrier_leakage` was left disconnected — it referenced a legacy `Well` API (`well.barrier_perm`, `well.compute_barrier_props`) that no longer exists, and was removed from `Pressure`. Re-wiring barrier leakage estimation against the current `Well`/`WellProcessed` API is separate future work.

**Exit criterion:** a WellClass user can define 2+ named pressure scenarios from a well and read back brine/CO2 pressure at a chosen depth, with test coverage, without pandas and without GaP involvement. Met except for the `get_values_at_depth` accessor.

**Status:** substantially complete. `Pressure`/`PressureScenario`/`PressureTable` are implemented, tested (`tests/well_class/test_pressure.py`, `tests/well_class/test_pressure_table.py`), and demonstrated in `01_wellclass.ipynb` through datum, explicit-datum-pressure, store-anchored, and MSAD-anchored scenarios.

### Checkpoint: 2026-08-21

The WellClass pressure path now has a coherent object boundary: `Pressure` owns background tables; `PressureScenario` owns its resolved anchor metadata and calculated fluid/brine curves. This is the point to pause pressure API expansion. The next pressure increment should be the small read-only `get_values_at_depth` accessor, not another anchor type or PVT model. Bundled CO2 PVT constants now live in package-owned data and are the normal `Pressure` default; `pvt_path` remains an explicit override for alternative collections.

### Phase 5: Reduce historical noise

Only after the supported path is tested:

1. Archive superseded notebooks and scripts outside the primary navigation.
2. Remove dead modules only when imports and documentation no longer reference them.
3. Delete stale comments that describe the old Well API.
4. Update README and MkDocs navigation to the canonical recipes.
5. Keep original data/code in a clearly labeled archive or separate history if it is still useful for provenance.

## Issue Candidates

These are good discrete issues, ordered by leverage:

1. **Add CI notebook smoke tests for the canonical recipes.**
2. **Document the WellClass-to-GaP dataframe contract and units.**
3. **Add vertical and deviated WellProcessed geometry fixtures.**
4. **Cover LGR bounding-box boundary cases.**
5. **Cover CARFIN output writers with golden text fixtures.**
6. **Model permeability assumptions explicitly.**
7. **Add a simulator dependency check and dry-run mode.**
8. **Migrate GaP mesh functions away from legacy `drilling_df` naming.**
9. **Classify and archive historical modules and notebooks.**
10. **Update README/MkDocs around the three supported workflows.**
11. **Publish and enforce the wellbore physical vocabulary.**
12. **Rename the WellClass-to-GaP boundary from drilling/casings/barriers to holes/casings/barrier regions.**
13. **Build a collections-based, multi-scenario WellClass pressure engine (brine + CO2, key-depth lookups) — see the pressure scenario engine backlog above.**

## Decision Rules

To avoid bloat:

- Do not add an abstraction unless a test demonstrates a repeated boundary or a real ownership problem.
- Prefer fixtures and contract tests over large snapshot files.
- Prefer pure functions for geometry and text generation.
- Keep simulator execution outside unit tests.
- Make units and coordinate systems visible in names or types.
- Fail at the boundary when required physics inputs are missing.
- Do not preserve an old API indefinitely without a migration owner and removal date.
- Every new workflow recipe must either become one of the canonical three or be clearly labeled experimental.

The roadmap owns sequencing and acceptance criteria. This document should not duplicate its backlog or retain dated implementation journals.
