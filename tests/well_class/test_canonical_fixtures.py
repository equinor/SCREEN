from pathlib import Path

import pytest

from src.WellClass.libs.well_class import WellProcessed


@pytest.mark.parametrize(
    ("fixture_name", "expected_boreholes"),
    [
        ("frigg/frigg.json", 5),
        ("simple_well/Simple_well.json", 3),
        ("smeaheia/smeaheia.json", 3),
        ("wildcat/wildcat.json", 4),
    ],
)
def test_canonical_json_fixture_processes(fixture_name, expected_boreholes):
    root = Path(__file__).parents[2]

    well = WellProcessed.from_json(root / "test_data/examples" / fixture_name)

    assert len(well.borehole or []) == expected_boreholes
