import numpy as np
import pytest

from src.WellClass.libs.grid_utils import (
    CoarseGridEnvelope,
    CoarseGridSpec,
    build_vertical_grid_schedule,
    format_vertical_grid_recipe,
    write_vertical_grid_recipe,
)


def test_coarse_grid_envelope_projects_deviated_wells_vertically():
    wells = [
        type("WellStub", (), {"wellpath": type("PathStub", (), {"x": [10.0, 20.0], "y": [0.0, 5.0]})(), "borehole": [{"top_tvd_msl": 100.0, "bottom_tvd_msl": 500.0}]})(),
        type("WellStub", (), {"wellpath": type("PathStub", (), {"x": [-5.0, 15.0], "y": [-10.0, 2.0]})(), "borehole": [{"top_tvd_msl": 50.0, "bottom_tvd_msl": 300.0}]})(),
    ]

    envelope = CoarseGridEnvelope.from_wells(wells, lateral_margin=2.0, vertical_margin=10.0)

    assert envelope == CoarseGridEnvelope(-7.0, 12.0, -12.0, 2.0, 40.0, 510.0)


def test_coarse_grid_envelope_rejects_missing_well_geometry():
    with pytest.raises(ValueError, match="at least one well"):
        CoarseGridEnvelope.from_wells([])

    well = type("WellStub", (), {"wellpath": None, "borehole": []})()
    with pytest.raises(ValueError, match="processed wellpath"):
        CoarseGridEnvelope.from_wells([well])


@pytest.mark.parametrize("field", ["lateral_margin", "vertical_margin"])
def test_coarse_grid_envelope_rejects_negative_margins(field):
    well = type("WellStub", (), {"wellpath": type("PathStub", (), {"x": [0.0], "y": [0.0]})(), "borehole": [{"top_tvd_msl": 0.0, "bottom_tvd_msl": 1.0}]})()

    with pytest.raises(ValueError, match=field):
        CoarseGridEnvelope.from_wells([well], **{field: -1.0})


def test_coarse_grid_envelope_rejects_unordered_bounds():
    with pytest.raises(ValueError, match="bounds must be ordered"):
        CoarseGridEnvelope(1.0, 0.0, 0.0, 1.0, 0.0, 1.0)


def test_vertical_schedule_covers_explicit_domain():
    spec = CoarseGridSpec(
        top_depth=4.0,
        water_depth=105.0,
        reservoir_top=2000.0,
        bottom_depth=2500.0,
        water_layers=1,
        overburden_layers=9,
        reservoir_layers=50,
    )

    schedule = build_vertical_grid_schedule(spec)

    assert len(schedule.dz) == 60
    assert schedule.sections.count("water") == 1
    assert schedule.sections.count("overburden") == 9
    assert schedule.sections.count("reservoir") == 50
    assert np.all(schedule.dz > 0)
    assert np.isclose(schedule.dz.sum(), spec.bottom_depth - spec.top_depth)
    assert np.isclose(schedule.depth_edges[-1], 2496.0)


def test_vertical_schedule_rejects_a_well_outside_domain():
    spec = CoarseGridSpec(top_depth=0.0, water_depth=100.0, reservoir_top=1000.0, bottom_depth=1500.0)
    well = type("WellStub", (), {"borehole": [{"top_tvd_msl": 0.0, "bottom_tvd_msl": 1600.0}]})()

    with pytest.raises(ValueError, match="does not cover well bottom"):
        build_vertical_grid_schedule(spec, well)


def test_vertical_schedule_rejects_a_well_above_domain():
    spec = CoarseGridSpec(top_depth=100.0, water_depth=200.0, reservoir_top=1000.0, bottom_depth=1500.0)
    well = type("WellStub", (), {"borehole": [{"top_tvd_msl": 50.0, "bottom_tvd_msl": 1200.0}]})()

    with pytest.raises(ValueError, match="does not cover well top"):
        build_vertical_grid_schedule(spec, well)


def test_vertical_recipe_formats_sections_and_lateral_cell_multiplier(tmp_path):
    spec = CoarseGridSpec(top_depth=4.0, water_depth=104.0, reservoir_top=1004.0, bottom_depth=1504.0, water_layers=1, overburden_layers=2, reservoir_layers=2)
    schedule = build_vertical_grid_schedule(spec)

    recipe = format_vertical_grid_recipe(spec, schedule, cells_per_layer=400)

    assert "TOPS 4 4* 1 1 /" in recipe
    assert "DZ\n400*100\n800*450\n800*250\n/" in recipe
    output_path = write_vertical_grid_recipe(spec, schedule, tmp_path / "tops_dz.inc", cells_per_layer=400)
    assert output_path.read_text(encoding="utf-8") == recipe


def test_vertical_recipe_rejects_invalid_lateral_cell_multiplier():
    spec = CoarseGridSpec(top_depth=0.0, water_depth=100.0, reservoir_top=1000.0, bottom_depth=1500.0)
    schedule = build_vertical_grid_schedule(spec)

    with pytest.raises(ValueError, match="cells_per_layer"):
        format_vertical_grid_recipe(spec, schedule, cells_per_layer=0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_depth": 100.0, "water_depth": 100.0, "reservoir_top": 1000.0, "bottom_depth": 1500.0},
        {"top_depth": 0.0, "water_depth": 100.0, "reservoir_top": 90.0, "bottom_depth": 1500.0},
        {"top_depth": 0.0, "water_depth": 100.0, "reservoir_top": 1000.0, "bottom_depth": 900.0},
    ],
)
def test_coarse_grid_spec_rejects_invalid_depth_order(kwargs):
    with pytest.raises(ValueError, match="top < water < reservoir top < bottom"):
        CoarseGridSpec(**kwargs)