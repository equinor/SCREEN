from pathlib import Path

import pandas as pd
import pytest

from src.WellClass.libs.utils.xlsx_parser import xlsx_grid_policy, xlsx_to_well_model


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
    survey = pd.read_excel(workbook, sheet_name="Survey", engine="openpyxl")

    assert model.spec.well_header.unique_wellbore_identifier == well_identifier
    assert policy["top_depth"] < model.spec.well_header.ground_elevation
    assert policy["water_depth"] == model.spec.well_header.ground_elevation
    assert policy["reservoir_permx"] == 1000.0
    assert policy["overburden_permx"] == 0.001
    assert survey.columns.tolist() == ["md_rkb", "inclination_deg", "azimuth_deg"]
    assert survey.empty
    if name == "smeaheia":
        assumptions = pd.read_excel(workbook, sheet_name="SubsurfaceAssumptions", engine="openpyxl")
        assert assumptions.loc[0, "z_fluid_contact"] == 1282.5
        assert assumptions.loc[0, "p_fluid_contact"] == 129.99
        assert assumptions.loc[0, "z_resrv"] == assumptions.loc[0, "z_fluid_contact"]
        assert assumptions.loc[0, "p_resrv"] == assumptions.loc[0, "p_fluid_contact"]
