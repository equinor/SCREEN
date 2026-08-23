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
- `build_vertical_grid_schedule` creates water, overburden, and reservoir `DZ` values.
- Well top/bottom coverage and invalid depth ordering are validated.
- `format_vertical_grid_recipe` and `write_vertical_grid_recipe` produce a simulator-oriented `TOPS`/`DZ` text recipe.
- Notebook 2 demonstrates the recipe against the Wildcat JSON fixture.
- A standalone preprocessing notebook demonstrates recipe generation and dry-run case staging:
    - [`04_init_case_preprocessing.ipynb`](../notebooks/04_init_case_preprocessing.ipynb)
- A workbook-driven adapter path stages init cases from a multi-sheet user input deck:
    - [`prepare_init_case_from_xlsx.py`](../runscripts/prepare_init_case_from_xlsx.py)
    - [`xlsx_parser.py`](../src/WellClass/libs/utils/xlsx_parser.py)
    - [`create_well_input_workbook.py`](../runscripts/create_well_input_workbook.py)
- Template assets now have explicit integrity checks in CI-focused tests:
    - [`test_template_assets.py`](../tests/gap/test_template_assets.py)

These helpers do not create native `.EGRID`/`.INIT` files or run a simulator.

## Next

1. Add a typed coarse-grid envelope containing lateral and vertical margins derived from `WellProcessed` geometry.
2. Extend workbook policy support from three-zone defaults to interval-aware policies (multi-reservoir capable) while keeping backward compatibility.
3. Add a pure-Python coverage report for an existing grid or grid specification:
   - required well envelope;
   - grid extents;
   - missing margins;
   - cell-size summary;
   - warnings and failure reasons.
4. Define a simulator backend interface that consumes the generated recipe and reports executable availability, command, logs, and output paths.
5. Add one simulator-backed dry-run path without invoking PFLOTRAN/CIRRUS in unit tests.
6. Connect a generated `.EGRID`/`.INIT` pair to notebook 3 as an optional generated-grid mode.

## Later

- Adapt or extend coarse cells when the well envelope is not covered.
- Preserve existing properties when adapting a grid.
- Support separate PFLOTRAN and CIRRUS input/output backends.
- Add a small committed synthetic grid for pure-Python tests.
- Replace hard-coded permeability and cell-size assumptions with modeled configuration.

## Boundaries

- Do not put coarse-grid creation inside `LGRBuilder`; it should receive a validated coarse grid.
- Keep simulator execution optional and explicit.
- Keep `TOPS`/`DZ` text generation separate from native EGRID/INIT generation.
- Keep units, depth coordinates, margins, and target cell sizes explicit.
- Preserve the existing pre-existing-grid workflow as a regression path.

The scripts in `experiments/legacy/` contain historical examples of tops generation, template handling, pressure initialization, and simulator orchestration. They are references for future work, not new implementation boundaries.
