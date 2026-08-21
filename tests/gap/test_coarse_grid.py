import numpy as np
import pytest

from src.WellClass.libs.grid_utils import CoarseGridSpec, build_vertical_grid_schedule


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