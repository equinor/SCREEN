from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
    well = make_vertical_well()
    frames = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)

    assert frames.holes_df is frames.drilling_df
    assert frames.plugs_df is frames.barriers_df
    assert frames.barrier_regions_df is frames.barriers_mod_df
    assert len(well.casing_cement) == 1
    assert len(well.cement_bond) == 1
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


def test_processed_well_permeability_is_millidarcy_and_nonnegative():
    with pytest.raises(ValueError, match="permeability_unit must be 'mD'"):
        WellDataFrame(make_vertical_well(), oh_perm=1.0, cb_perm=1.0, barrier_perm=1.0, permeability_unit="D")

    with pytest.raises(ValueError, match="finite and nonnegative in mD"):
        WellDataFrame(make_vertical_well(), oh_perm=-1.0, cb_perm=1.0, barrier_perm=1.0)


def test_scenario_permeability_override_changes_material_not_geometry():
    well = make_vertical_well()
    baseline = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)
    sensitivity = WellDataFrame(
        well,
        oh_perm=10000.0,
        cb_perm=0.05,
        barrier_perm=0.05,
        permeability_overrides={"cb_perm": 0.2},
    )

    geometry_columns = ["diameter_m", "top_msl", "bottom_msl", "toc_msl", "boc_msl"]
    pd.testing.assert_frame_equal(baseline.casings_df[geometry_columns], sensitivity.casings_df[geometry_columns])
    assert baseline.casings_df["cb_perm"].tolist() == [0.05]
    assert sensitivity.casings_df["cb_perm"].tolist() == [0.2]


def test_interval_permeability_overrides_only_change_selected_smeaheia_intervals():
    root = Path(__file__).parents[2]
    well = WellProcessed.from_json(root / "test_data/examples/smeaheia/smeaheia.json")
    baseline = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)
    sensitivity = WellDataFrame(
        well,
        oh_perm=10000.0,
        cb_perm=0.05,
        barrier_perm=0.05,
        interval_permeability_overrides={
            "cb_perm": {"Cement 9 5/8 in": 0.25},
            "barrier_perm": {"cplug9": 0.75},
        },
    )

    geometry_columns = ["diameter_m", "top_msl", "bottom_msl", "toc_msl", "boc_msl"]
    pd.testing.assert_frame_equal(baseline.casings_df[geometry_columns], sensitivity.casings_df[geometry_columns])
    pd.testing.assert_frame_equal(
        baseline.barrier_regions_df[["barrier_name", "top_msl", "bottom_msl", "diameter_m"]],
        sensitivity.barrier_regions_df[
            ["barrier_name", "top_msl", "bottom_msl", "diameter_m"]
        ],
    )
    baseline_cement = baseline.casings_df.set_index("cement_name")["cb_perm"]
    selected_cement = sensitivity.casings_df.set_index("cement_name")["cb_perm"]
    baseline_plugs = baseline.barrier_regions_df.set_index("barrier_name")["barrier_perm"]
    selected_plugs = sensitivity.barrier_regions_df.set_index("barrier_name")["barrier_perm"]
    assert selected_cement["Cement 9 5/8 in"] == 0.25
    pd.testing.assert_series_equal(
        selected_cement.drop("Cement 9 5/8 in"),
        baseline_cement.drop("Cement 9 5/8 in"),
        check_dtype=False,
    )
    assert selected_plugs["cplug9"] == 0.75
    pd.testing.assert_series_equal(selected_plugs.drop("cplug9"), baseline_plugs.drop("cplug9"), check_dtype=False)


def test_interval_permeability_override_rejects_unknown_names():
    well = WellProcessed.from_json(Path(__file__).parents[2] / "test_data/examples/smeaheia/smeaheia.json")
    with pytest.raises(ValueError, match="unknown plug interval 'missing'"):
        WellDataFrame(
            well,
            oh_perm=10000.0,
            cb_perm=0.05,
            barrier_perm=0.05,
            interval_permeability_overrides={"barrier_perm": {"missing": 0.2}},
        )