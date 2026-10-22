import numpy as np
import pytest

from src.GaP.libs.models.simulation_scenario import SimulationScenario
from src.GaP.libs.pressure_inputs import resolve_pressure_inputs
from src.WellClass.libs.models.well_model_utils import WellHeaderModel
from src.WellClass.libs.well_pressure.pressure_scenario import PressureScenario
from src.WellClass.libs.well_pressure.pressure_table import PressureTable


@pytest.fixture
def header():
    return WellHeaderModel(
        unique_wellbore_identifier="NO 32/4-1",
        depth_reference_rkb=23.5,
        depth_reference_rkb_unit="m",
        ground_elevation=312.0,
        ground_elevation_unit="m",
        total_depth_rkb=3186.0,
        total_depth_rkb_unit="m",
    )


def test_contact_depth_only_uses_hydrostatic_pressure(header):
    scenario = SimulationScenario(z_fluid_contact=1400.0)
    resolved = resolve_pressure_inputs(scenario, header)
    table = PressureTable(
        name="expected",
        depth=np.array([0.0, 1400.0]),
        ground_elevation=header.ground_elevation,
        ground_temperature=4.0,
        geothermal_gradient=31.0,
        salinity=0.032,
    )
    assert resolved.p_fluid_contact == pytest.approx(table.hydrostatic_pressure[-1])
    assert resolved.z_resrv == resolved.z_fluid_contact == 1400.0
    assert resolved.p_resrv == resolved.p_fluid_contact
    assert scenario.p_fluid_contact is None
    assert scenario.z_resrv is None


def test_explicit_contact_pair_is_the_reservoir_pair(header):
    resolved = resolve_pressure_inputs(SimulationScenario(z_fluid_contact=1400.0, p_fluid_contact=125.0), header)
    assert resolved.p_fluid_contact == resolved.p_resrv == 125.0
    assert resolved.z_fluid_contact == resolved.z_resrv == 1400.0


@pytest.mark.parametrize("contact", [1217.0, 1218.0, 1222.0, 1400.0])
@pytest.mark.parametrize("reservoir_pressure", [120.0, 125.0, 130.0, 140.0])
def test_reservoir_pair_anchors_the_curve(header, contact, reservoir_pressure):
    resolved = resolve_pressure_inputs(
        SimulationScenario(z_resrv=1217.0, p_resrv=reservoir_pressure, z_fluid_contact=contact), header
    )
    assert resolved.z_resrv == 1217.0
    assert resolved.p_resrv == reservoir_pressure
    assert resolved.z_fluid_contact == contact
    if contact == 1217.0:
        assert resolved.p_fluid_contact == reservoir_pressure
    else:
        assert resolved.p_fluid_contact > reservoir_pressure
    round_trip = resolve_pressure_inputs(resolved, header)
    assert round_trip == resolved


def test_reservoir_curve_uses_existing_variable_density_integrator(header):
    table = PressureTable(
        name="expected",
        depth=np.array([0.0, 1217.0, 1400.0, 3600.0]),
        ground_elevation=header.ground_elevation,
        ground_temperature=4.0,
        geothermal_gradient=31.0,
        salinity=0.032,
    )
    expected = PressureScenario(name="expected", table=table, z_fluid_datum=1400.0, z_store=1217.0, p_store=125.0)
    resolved = resolve_pressure_inputs(SimulationScenario(z_resrv=1217.0, p_resrv=125.0, z_fluid_contact=1400.0), header)
    assert resolved.p_fluid_contact == pytest.approx(expected.p_fluid_datum)


def test_reservoir_pair_only_becomes_contact_pair(header):
    resolved = resolve_pressure_inputs(SimulationScenario(z_resrv=1217.0, p_resrv=125.0), header)
    assert resolved.z_fluid_contact == resolved.z_resrv == 1217.0
    assert resolved.p_fluid_contact == resolved.p_resrv == 125.0


@pytest.mark.parametrize("values, message", [
    ({}, "provide z_fluid_contact"),
    ({"p_fluid_contact": 125.0}, "requires z_fluid_contact"),
    ({"z_resrv": 1217.0}, "must be provided together"),
    ({"p_resrv": 125.0, "z_fluid_contact": 1400.0}, "must be provided together"),
    ({"z_resrv": 1400.0, "p_resrv": 125.0, "z_fluid_contact": 1217.0}, "cannot be deeper"),
    ({"z_resrv": 1217.0, "p_resrv": 125.0, "z_fluid_contact": 1400.0, "p_fluid_contact": 125.0}, "conflicts"),
    ({"z_resrv": 1217.0, "p_resrv": 125.0, "z_fluid_contact": 1217.0, "p_fluid_contact": 130.0}, "conflicts"),
    ({"z_fluid_contact": 100.0}, "deeper than ground_elevation"),
])
def test_invalid_pressure_inputs_fail_explicitly(header, values, message):
    with pytest.raises(ValueError, match=message):
        resolve_pressure_inputs(SimulationScenario(**values), header)


def test_rounded_consistent_pressure_pairs_are_accepted(header):
    source = SimulationScenario(z_resrv=1217.0, p_resrv=125.0, z_fluid_contact=1400.0)
    resolved = resolve_pressure_inputs(source, header)
    rounded = source.model_copy(update={"p_fluid_contact": round(resolved.p_fluid_contact, 2)})
    assert resolve_pressure_inputs(rounded, header).p_fluid_contact == resolved.p_fluid_contact
