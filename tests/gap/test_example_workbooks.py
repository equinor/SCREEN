from pathlib import Path

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

    assert model.spec.well_header.unique_wellbore_identifier == well_identifier
    assert policy["top_depth"] < policy["water_depth"] < policy["reservoir_top"] < policy["bottom_depth"]
