import numpy as np
import pandas as pd

from src.WellClass.libs.well_pressure.co2_pressure import _get_max_pressure, _get_shmin


def make_pressure_table():
    return pd.DataFrame(
        {
            "depth_msl": [0.0, 10.0, 20.0, 30.0],
            "temp": [4.0, 4.0, 4.0, 4.0],
            "hs_p": [1.0, 2.0, 3.0, 4.0],
        }
    )


def constant_density(_pressure, _temperature):
    return np.array([[1000.0]])


def test_shmin_matches_hydrostatic_above_seafloor():
    table = _get_shmin({"sf_depth_msl": 10.0}, make_pressure_table())

    assert table.loc[0, "Shmin"] == 1.0
    assert table.loc[1, "Shmin"] == 2.0
    assert table.loc[2, "Shmin"] > table.loc[1, "Shmin"]


def test_max_pressure_accepts_scalar_and_list_positions():
    header = {"sf_temp": 4.0, "sf_depth_msl": 0.0, "geo_tgrad": 40.0}
    table = _get_shmin(header, make_pressure_table())

    result = _get_max_pressure(table, [10.0, 20.0], constant_density, header)

    assert {"max_pressure_at_10", "max_pressure_at_20"} <= set(result)
    assert result.loc[3, "max_pressure_at_10"] > result.loc[1, "max_pressure_at_10"]
    assert result.loc[3, "max_pressure_at_20"] > result.loc[2, "max_pressure_at_20"]


def test_max_pressure_uses_plug_base_for_position_table():
    header = {"sf_temp": 4.0, "sf_depth_msl": 0.0, "geo_tgrad": 40.0}
    table = _get_shmin(header, make_pressure_table())
    plugs = {
        "barrier_name": {0: "cement_plug"},
        "bottom_msl": {0: 10.0},
    }

    result = _get_max_pressure(table, plugs, constant_density, header)

    assert "max_pressure_cement_plug" in result
    assert result.loc[1, "max_pressure_cement_plug"] == table.loc[1, "Shmin"]


def test_canonical_plug_positions_match_legacy_barrier_table():
    header = {"sf_temp": 4.0, "sf_depth_msl": 0.0, "geo_tgrad": 40.0}
    table = _get_shmin(header, make_pressure_table())
    legacy = {"barrier_name": {0: "cement_plug"}, "bottom_msl": {0: 10.0}}
    canonical = [{"name": "cement_plug", "base_tvd_msl": 10.0}]

    legacy_result = _get_max_pressure(table, legacy, constant_density, header)
    canonical_result = _get_max_pressure(table, canonical, constant_density, header)

    assert canonical_result["max_pressure_cement_plug"].equals(legacy_result["max_pressure_cement_plug"])