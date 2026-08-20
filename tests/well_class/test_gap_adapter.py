import numpy as np

from src.WellClass.libs.grid_utils import WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


def make_vertical_well() -> WellProcessed:
    return WellProcessed(
        header={
            "unique_wellbore_identifier": "synthetic",
            "depth_reference_rkb": 0.0,
            "depth_reference_rkb_unit": "m",
            "ground_elevation": 0.0,
            "ground_elevation_unit": "m",
            "total_depth_rkb": 1000.0,
            "total_depth_rkb_unit": "m",
        },
        hole_casings=[
            {
                "name": "hole 17.5",
                "type": "hole",
                "top_rkb": 0.0,
                "bottom_rkb": 600.0,
                "diameter_in": 17.5,
            },
            {
                "name": "hole 12.25",
                "type": "hole",
                "top_rkb": 600.0,
                "bottom_rkb": 1000.0,
                "diameter_in": 12.25,
            },
            {
                "name": "casing 13.375",
                "type": "casing",
                "top_rkb": 0.0,
                "bottom_rkb": 600.0,
                "diameter_in": 13.375,
            },
            {
                "name": "cement 13.375",
                "type": "casing cement",
                "top_rkb": 0.0,
                "bottom_rkb": 600.0,
                "diameter_in": 13.375,
            },
        ],
    )


def test_processed_vertical_well_exposes_gap_contract():
    frames = WellDataFrame(make_vertical_well(), oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)

    assert frames.holes_df is frames.drilling_df
    assert frames.barrier_regions_df is frames.barriers_mod_df
    assert list(frames.drilling_df["top_msl"]) == [0.0, 600.0]
    assert list(frames.drilling_df["bottom_msl"]) == [600.0, 1000.0]
    assert np.allclose(frames.drilling_df["diameter_m"], [0.4445, 0.31115])
    assert {"oh_perm", "diameter_m", "top_msl", "bottom_msl"} <= set(frames.drilling_df)

    casing = frames.casings_df.iloc[0]
    assert np.allclose(casing[["top_msl", "bottom_msl", "toc_msl", "boc_msl"]], [0.0, 600.0, 0.0, 600.0])
    assert {"cb_perm", "diameter_m", "top_msl", "bottom_msl", "toc_msl", "boc_msl"} <= set(frames.casings_df)

    assert np.isclose(frames.annulus_df.loc[0, "thick_m"], 0.0523875)


def test_processed_well_requires_explicit_permeability():
    try:
        WellDataFrame(make_vertical_well())
    except ValueError as error:
        assert str(error) == "oh_perm must be provided for processed wells"
    else:
        raise AssertionError("Expected missing open-hole permeability to fail")