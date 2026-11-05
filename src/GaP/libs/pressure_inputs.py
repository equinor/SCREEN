"""Resolve workbook contact and reservoir pressure datums using WellClass."""

from math import isclose
import warnings

import numpy as np

from src.GaP.libs.models.simulation_scenario import SimulationScenario
from src.WellClass.libs.models.well_model_utils import WellHeaderModel
from src.WellClass.libs.well_pressure.pressure_scenario import PressureScenario
from src.WellClass.libs.well_pressure.pressure_table import PressureTable


def resolve_pressure_inputs(scenario: SimulationScenario, header: WellHeaderModel) -> SimulationScenario:
    """Return a copy with complete, consistent contact and reservoir pairs."""
    contact_depth = scenario.z_fluid_contact
    reservoir_depth, reservoir_pressure = scenario.z_resrv, scenario.p_resrv
    if contact_depth is None:
        if scenario.p_fluid_contact is not None:
            raise ValueError("p_fluid_contact requires z_fluid_contact")
        if reservoir_depth is None and reservoir_pressure is None:
            raise ValueError("provide z_fluid_contact or a complete z_resrv/p_resrv pair")

    # Include both datum depths explicitly, avoiding interpolation across the anchor.
    datums = [value for value in (contact_depth, reservoir_depth) if value is not None]
    bottom = max([*datums, header.total_depth_rkb - header.depth_reference_rkb]) + 500.0
    depth = np.unique(np.concatenate((np.arange(0.0, bottom + 10.0, 10.0), datums)))
    table = PressureTable(
        name="workbook",
        depth=depth,
        ground_elevation=header.ground_elevation,
        ground_temperature=scenario.ground_temperature,
        geothermal_gradient=scenario.temperature_gradient,
        salinity=scenario.salinity,
    )
    reference_below_contact = (
        contact_depth is not None and reservoir_depth is not None
        and reservoir_pressure is not None and reservoir_depth > contact_depth
    )
    contact_anchor = scenario.p_fluid_contact if reservoir_depth is None else None
    if reference_below_contact:
        contact_anchor = float(
            reservoir_pressure
            + np.interp(contact_depth, table.depth, table.hydrostatic_pressure)
            - np.interp(reservoir_depth, table.depth, table.hydrostatic_pressure)
        )
    pressure = PressureScenario(
        name=scenario.case_name,
        table=table,
        z_fluid_datum=contact_depth,
        p_fluid_datum=contact_anchor,
        z_store=None if reference_below_contact else reservoir_depth,
        p_store=None if reference_below_contact else reservoir_pressure,
        fluid_type=scenario.fluid_type,
    )
    contact_pressure = pressure.p_fluid_datum
    contact_depth = pressure.z_fluid_datum
    if contact_pressure is None or not np.isfinite(contact_pressure):
        raise ValueError("could not resolve a finite pressure at z_fluid_contact")
    if scenario.p_fluid_contact is not None and not isclose(scenario.p_fluid_contact, contact_pressure, rel_tol=0.0, abs_tol=0.01):
        raise ValueError(
            f"p_fluid_contact={scenario.p_fluid_contact:g} bar conflicts with "
            f"the reference-derived pressure {contact_pressure:g} bar at z_fluid_contact={contact_depth:g} m "
            "(tolerance 0.01 bar); provide only one pressure pair or consistent pairs"
        )
    if reference_below_contact:
        warnings.warn(
            f"Case {scenario.case_name!r}: reservoir reference at {reservoir_depth:g} m is below "
            f"the contact at {contact_depth:g} m; using the reference-anchored brine gradient "
            f"to derive contact pressure {contact_pressure:g} bar and anchor the CO2 curve there. "
            "The supplied reservoir reference pair is unchanged.",
            stacklevel=2,
        )
    return scenario.model_copy(update={
        "z_fluid_contact": contact_depth,
        "p_fluid_contact": contact_pressure,
        "z_resrv": reservoir_depth if reference_below_contact else pressure.z_store,
        "p_resrv": reservoir_pressure if reference_below_contact else pressure.p_store,
    })
