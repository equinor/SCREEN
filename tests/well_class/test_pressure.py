from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.WellClass.libs.well_pressure.co2_pressure import _get_max_pressure, _get_shmin, _integrate_pressure
from src.WellClass.libs.well_pressure.pressure import Pressure
from src.WellClass.libs.well_pressure.pressure_scenario import PressureScenario
from src.WellClass.libs.well_pressure.pressure_table import PressureTable

PVT_PATH = Path(__file__).resolve().parents[2] / "test_data" / "pvt_constants"


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


def test_pressure_integration_increases_downward_and_decreases_upward():
    header = {"sf_temp": 4.0, "sf_depth_msl": 0.0, "geo_tgrad": 40.0}
    table = make_pressure_table()

    downward = _integrate_pressure(header, table, constant_density, 10.0, 100.0, "down", "downward")
    upward = _integrate_pressure(header, table, constant_density, 20.0, 100.0, "up", "upward")

    assert downward.loc[1, "downward"] == pytest.approx(100.0)
    assert downward.loc[3, "downward"] > downward.loc[1, "downward"]
    assert upward.loc[2, "upward"] == pytest.approx(100.0)
    assert upward.loc[0, "upward"] < upward.loc[2, "upward"]


def make_test_table():
    return PressureTable(
        name="test",
        depth=np.arange(0.0, 1001.0, 10.0),
        ground_elevation=100.0,
        ground_temperature=4.0,
        geothermal_gradient=40.0,
        shmin_gradient=0.1695,
    )


def test_pressure_scenario_defaults_to_hydrostatic_brine_pressure():
    table = make_test_table()

    scenario = PressureScenario(name="default", table=table, z_fluid_datum=500.0, fluid_gradient=0.06)

    assert np.array_equal(scenario.brine_pressure, table.hydrostatic_pressure)
    expected_pressure = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.p_fluid_datum == pytest.approx(expected_pressure)
    assert scenario.p_delta == 0.0
    assert scenario.z_store == 500.0
    assert scenario.p_store == pytest.approx(expected_pressure)


def test_pressure_scenario_fixed_gradient_extrapolates_from_datum():
    table = make_test_table()

    scenario = PressureScenario(name="fixed_gradient", table=table, z_fluid_datum=500.0, fluid_gradient=0.05)

    p0 = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.fluid_pressure[table.depth == 500.0][0] == pytest.approx(p0)
    assert scenario.fluid_pressure[table.depth == 600.0][0] == pytest.approx(p0 + 0.05 * 100)


def test_pressure_scenario_fluid_datum_pressure_updates_delta_and_brine_curve():
    table = make_test_table()

    scenario = PressureScenario(name="overpressured", table=table, z_fluid_datum=500.0, p_fluid_datum=300.0, fluid_gradient=0.05)

    hydrostatic_at_500 = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.p_delta == pytest.approx(300.0 - hydrostatic_at_500)
    assert np.array_equal(scenario.brine_pressure, table.hydrostatic_pressure + scenario.p_delta)
    assert scenario.fluid_pressure[table.depth == 500.0][0] == pytest.approx(300.0)
    assert scenario.z_store == 500.0
    assert scenario.p_store == 300.0


def test_pressure_scenario_delta_derives_fluid_datum_pressure_and_brine_curve():
    table = make_test_table()

    scenario = PressureScenario(name="delta_overpressure", table=table, z_fluid_datum=500.0, p_delta=24.0, fluid_gradient=0.05)

    hydrostatic_at_500 = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.p_fluid_datum == pytest.approx(hydrostatic_at_500 + 24.0)
    assert scenario.fluid_pressure[table.depth == 500.0][0] == pytest.approx(scenario.p_fluid_datum)
    assert np.array_equal(scenario.brine_pressure, table.hydrostatic_pressure + 24.0)


def test_pressure_scenario_rejects_datum_pressure_and_delta_together():
    table = make_test_table()

    with pytest.raises(ValueError, match="either p_fluid_datum or p_delta"):
        PressureScenario(name="ambiguous_datum", table=table, z_fluid_datum=500.0, p_fluid_datum=300.0, p_delta=24.0, fluid_gradient=0.05)


def test_pressure_scenario_store_pair_becomes_datum_when_no_datum_is_supplied():
    table = make_test_table()

    scenario = PressureScenario(name="store_only", table=table, z_store=500.0, p_store=300.0, fluid_gradient=0.05)

    hydrostatic_at_500 = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.z_fluid_datum == 500.0
    assert scenario.p_fluid_datum == 300.0
    assert scenario.p_delta == pytest.approx(300.0 - hydrostatic_at_500)
    assert scenario.fluid_pressure[table.depth == 500.0][0] == pytest.approx(300.0)


def test_pressure_scenario_store_pair_anchors_curve_and_derives_datum_pressure():
    table = make_test_table()

    scenario = PressureScenario(name="store_anchor", table=table, z_fluid_datum=500.0, z_store=400.0, p_store=180.0, fluid_gradient=0.05)

    hydrostatic_at_500 = float(np.interp(500.0, table.depth, table.hydrostatic_pressure))
    assert scenario.fluid_pressure[table.depth == 400.0][0] == pytest.approx(180.0)
    assert scenario.p_fluid_datum == pytest.approx(185.0)
    assert scenario.p_delta == pytest.approx(185.0 - hydrostatic_at_500)


def test_pressure_scenario_rejects_store_deeper_than_datum():
    table = make_test_table()

    with pytest.raises(ValueError, match="cannot be deeper"):
        PressureScenario(name="invalid_order", table=table, z_fluid_datum=500.0, z_store=600.0, p_store=180.0, fluid_gradient=0.05)


def test_pressure_scenario_rejects_datum_at_or_above_ground_elevation():
    table = make_test_table()

    with pytest.raises(ValueError, match="deeper than ground_elevation"):
        PressureScenario(name="shallow_datum", table=table, z_fluid_datum=100.0, fluid_gradient=0.05)


def test_pressure_builds_default_scenario_from_co2_datum(tmp_path=None):
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}

    pressure = Pressure(
        header=header,
        co2_datum=500.0,
        pvt_path=str(PVT_PATH),
        ground_temperature=4.0,
        geothermal_gradient=40.0,
    )

    assert "default" in pressure.scenarios
    assert pressure.scenarios["default"].z_fluid_datum == 500.0
    assert not np.isnan(pressure.scenarios["default"].p_MSAD)


def test_pressure_can_be_built_from_explicit_geometry():
    pressure = Pressure(
        ground_elevation=100.0,
        total_depth_rkb=1000.0,
        depth_reference_rkb=25.0,
        co2_datum=500.0,
        pvt_path=str(PVT_PATH),
        ground_temperature=4.0,
        geothermal_gradient=40.0,
    )

    assert pressure.header is None
    assert pressure.table.ground_elevation == 100.0
    assert pressure.scenarios["default"].z_fluid_datum == 500.0


def test_pressure_requires_all_explicit_geometry_without_header():
    with pytest.raises(ValueError, match="Provide header or explicit geometry values"):
        Pressure(
            ground_elevation=100.0,
            total_depth_rkb=1000.0,
            co2_datum=500.0,
            pvt_path=str(PVT_PATH),
            ground_temperature=4.0,
            geothermal_gradient=40.0,
        )


def test_pressure_header_geometry_takes_precedence_over_explicit_values():
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(
        header=header,
        ground_elevation=999.0,
        total_depth_rkb=9999.0,
        depth_reference_rkb=999.0,
        co2_datum=500.0,
        pvt_path=str(PVT_PATH),
        ground_temperature=4.0,
        geothermal_gradient=40.0,
    )

    assert pressure.table.ground_elevation == 100.0
    assert pressure.total_depth_rkb == 1000.0


def test_pressure_add_scenario_shares_the_same_table():
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(header=header, co2_datum=500.0, pvt_path=str(PVT_PATH), ground_temperature=4.0, geothermal_gradient=40.0)

    scenario = pressure.add_scenario("plug_scenario", z_fluid_datum=200.0, fluid_gradient=0.05)

    assert scenario.table is pressure.table
    assert pressure.scenarios["plug_scenario"] is scenario


def test_pressure_rejects_duplicate_scenario_names():
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(header=header, co2_datum=500.0, pvt_path=str(PVT_PATH), ground_temperature=4.0, geothermal_gradient=40.0)

    with pytest.raises(ValueError, match="already exists"):
        pressure.add_scenario("default", z_fluid_datum=200.0, fluid_gradient=0.05)


def test_pressure_add_table_supports_geothermal_gradient_sensitivity():
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(header=header, co2_datum=500.0, pvt_path=str(PVT_PATH), ground_temperature=4.0, geothermal_gradient=40.0)

    hot_table = pressure.add_table("hot", geothermal_gradient=60.0)
    hot_scenario = pressure.add_scenario("hot_default", table_name="hot", z_fluid_datum=500.0, fluid_gradient=0.05)

    assert hot_table is not pressure.table
    assert hot_scenario.table is hot_table
    assert hot_table.temperature[-1] > pressure.table.temperature[-1]


def test_pressure_add_table_rejects_duplicate_names():
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(header=header, co2_datum=500.0, pvt_path=str(PVT_PATH), ground_temperature=4.0, geothermal_gradient=40.0)

    with pytest.raises(ValueError, match="already exists"):
        pressure.add_table("default")


def test_pressure_scenario_pvt_integration_matches_water_density_hydrostatic():
    """A brine-density fluid integrated via the PVT path should roughly reproduce
    the table's own constant-density hydrostatic curve near msl (low pressure/temp)."""
    header = {"ground_elevation": 100.0, "total_depth_rkb": 1000.0, "depth_reference_rkb": 25.0}
    pressure = Pressure(header=header, co2_datum=500.0, pvt_path=str(PVT_PATH), ground_temperature=4.0, geothermal_gradient=40.0)

    scenario = pressure.scenarios["default"]

    # fluid_pressure should be monotonically increasing with depth on each side of the datum
    below_datum = scenario.fluid_pressure[pressure.table.depth >= 500.0]
    assert np.all(np.diff(below_datum) >= 0)