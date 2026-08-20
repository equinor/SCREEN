import numpy as np

from src.WellClass.libs.well_class import WellProcessed


def make_well(**overrides):
    header = {
        "unique_wellbore_identifier": "test-well",
        "depth_reference_rkb": 0.0,
        "depth_reference_rkb_unit": "m",
        "ground_elevation": 0.0,
        "ground_elevation_unit": "m",
        "total_depth_rkb": 1000.0,
        "total_depth_rkb_unit": "m",
    }
    header.update(overrides.pop("header", {}))
    return WellProcessed(
        header=header,
        hole_casings=overrides.pop(
            "hole_casings",
            [{"name": "hole", "type": "hole", "top_rkb": 0.0, "bottom_rkb": 1000.0, "diameter_in": 12.25}],
        ),
        survey=overrides.pop("survey", None),
        **overrides,
    )


def test_feet_depths_are_converted_before_tvd_processing():
    well = make_well(
        header={
            "depth_reference_rkb": 100.0,
            "depth_reference_rkb_unit": "ft",
            "total_depth_rkb": 1000.0,
            "total_depth_rkb_unit": "ft",
        },
        hole_casings=[{"name": "hole", "type": "hole", "top_rkb": 0.0, "bottom_rkb": 1000.0, "diameter_in": 12.25}],
    )

    assert np.isclose(well.header["depth_reference_rkb"], 30.48)
    assert np.isclose(well.header["total_depth_rkb"], 304.8)
    assert np.isclose(well.hole_casings[0]["bottom_rkb"], 304.8)
    assert np.isclose(float(well.md2tvd(304.8)), 274.32)


def test_deviated_survey_produces_tvd_below_measured_depth():
    well = make_well(
        header={"total_depth_rkb": 1000.0},
        survey={
            "md_rkb": [0.0, 500.0, 1000.0],
            "inclination_deg": [0.0, 45.0, 45.0],
            "azimuth_deg": [0.0, 0.0, 0.0],
        },
    )

    assert float(well.md2tvd(1000.0)) < 1000.0