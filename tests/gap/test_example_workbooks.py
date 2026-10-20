from pathlib import Path

import pandas as pd
import pytest

from src.GaP.libs.models.simulation_scenario import SimulationScenario
from src.WellClass.libs.utils.xlsx_parser import GridPolicy, xlsx_grid_policy, xlsx_to_simulation_design, xlsx_to_well_model


@pytest.mark.parametrize(
    ("name", "well_identifier"),
    [
        ("wildcat", "NO 17/4-1"),
        ("smeaheia", "NO 32/4-1"),
    ],
)
def test_example_workbooks_parse_to_canonical_wells(name, well_identifier):
    root = Path(__file__).parents[2]
    workbook = root / f"test_data/examples/{name}/{name}_workbook.xlsx"

    model = xlsx_to_well_model(workbook)
    policy = xlsx_grid_policy(workbook)
    design = xlsx_to_simulation_design(workbook)
    survey = pd.read_excel(workbook, sheet_name="Survey", engine="openpyxl")

    assert model.spec.well_header.unique_wellbore_identifier == well_identifier
    assert policy["top_depth"] < model.spec.well_header.ground_elevation
    assert policy["water_depth"] == model.spec.well_header.ground_elevation
    assert policy["reservoir_permx"] == 1000.0
    assert policy["overburden_permx"] == 0.001
    assert all(scenario.depth_unit == "m" for scenario in design.scenarios)
    assert all(scenario.pressure_unit == "bar" for scenario in design.scenarios)
    assert all(scenario.salinity_basis == "mass_fraction" for scenario in design.scenarios)
    assert all(scenario.permeability_unit == "mD" for scenario in design.scenarios)
    assert all(scenario.cb_perm_interval == "ALL" for scenario in design.scenarios)
    assert all(scenario.barrier_perm_interval == "ALL" for scenario in design.scenarios)
    assert survey.columns.tolist() == ["md_rkb", "inclination_deg", "azimuth_deg"]
    assert survey.empty
    if name == "smeaheia":
        assumptions = pd.read_excel(workbook, sheet_name="DesignMatrix", engine="openpyxl")
        assert assumptions.loc[0, "z_fluid_contact"] == 1282.5
        assert assumptions.loc[0, "p_fluid_contact"] == 129.99
        assert assumptions.loc[0, "z_resrv"] == assumptions.loc[0, "z_fluid_contact"]
        assert assumptions.loc[0, "p_resrv"] == assumptions.loc[0, "p_fluid_contact"]


def test_every_scenario_and_grid_policy_field_is_documented():
    """The "Parameters you can sensitise per case" section of the GaP README must name every field."""
    readme = (Path(__file__).parents[2] / "src/GaP/README.md").read_text(encoding="utf-8")
    start = readme.index("### Parameters you can sensitise per case")
    section = readme[start : readme.index("\n### ", start + 1)]
    missing = [
        name for name in (*SimulationScenario.model_fields, *GridPolicy.model_fields) if f"`{name}`" not in section
    ]
    assert not missing, f"add these to the README sensitivity section: {missing}"
