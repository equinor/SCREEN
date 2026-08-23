import pytest

from src.WellClass.libs.well_computed.plug_properties import compute_plug_properties
from src.WellClass.libs.well_computed.plugs_diameter import compute_plugs_diameter


def make_plug(top=400.0, bottom=600.0):
    return {
        "name": "cement_plug",
        "top_rkb": top,
        "bottom_rkb": bottom,
        "tvd_msl_top": top,
        "tvd_msl_bottom": bottom,
        "cement_perm": 0.05,
    }


def make_borehole():
    return [
        {"top_rkb": 0.0, "bottom_rkb": 500.0, "top_tvd_msl": 0.0, "bottom_tvd_msl": 500.0, "diameter_m": 0.4},
        {"top_rkb": 500.0, "bottom_rkb": 1000.0, "top_tvd_msl": 500.0, "bottom_tvd_msl": 1000.0, "diameter_m": 0.3},
    ]


def test_plug_in_one_borehole_section_keeps_one_diameter():
    segments = compute_plugs_diameter([make_plug(100.0, 200.0)], make_borehole())

    assert len(segments) == 1
    assert segments[0]["segment"] == 0
    assert segments[0]["diameter_m"] == 0.4


def test_plug_crossing_borehole_sections_is_split():
    segments = compute_plugs_diameter([make_plug()], make_borehole())

    assert [(item["top_rkb"], item["bottom_rkb"]) for item in segments] == [(400.0, 500.0), (500.0, 600.0)]
    assert [item["diameter_m"] for item in segments] == [0.4, 0.3]


def test_plug_properties_uses_length_weighted_average_diameter():
    segments = compute_plugs_diameter([make_plug()], make_borehole())

    properties = compute_plug_properties(segments, ["cement_plug"], "cement_plug")

    assert properties["top_rkb"] == 400.0
    assert properties["bottom_rkb"] == 600.0
    assert properties["thickness_md"] == 200.0
    assert properties["radius"] == pytest.approx(0.175)


def test_plug_outside_borehole_is_rejected():
    with pytest.raises(ValueError, match="do not overlap"):
        compute_plugs_diameter([make_plug(-10.0, 0.0)], make_borehole())