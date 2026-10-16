from datetime import date
from pathlib import Path
import re

import pytest

from src.GaP.libs.deck_config import CirrusDeckParameters, parameterize_cirrus_deck


TEMPLATE = Path(__file__).parents[2] / "test_data/examples/wildcat-pflotran/model/TEMP-0.in"


def parameters(salinity: float) -> CirrusDeckParameters:
    return CirrusDeckParameters(
        start_date=date(2025, 1, 1),
        final_date=date(2125, 1, 1),
        top_depth=4,
        seafloor_depth=105,
        bottom_depth=2400,
        overburden_datum_depth=500,
        overburden_pressure_bar=50,
        fluid_contact_depth=2400,
        fluid_contact_pressure_bar=210,
        salinity_mass_fraction=salinity,
    )


@pytest.mark.parametrize("salinity", [0.0, 0.032, 0.04, 0.1])
def test_brine_matches_salt_tables_and_is_idempotent(tmp_path, salinity):
    deck = tmp_path / "case.in"
    deck.write_text(TEMPLATE.read_text())
    parameterize_cirrus_deck(deck, parameters(salinity))
    text = deck.read_text()

    assert re.findall(r"(?m)^\s*BRINE\s+(.+)$", text) == [f"{salinity:g} MASS"]
    assert text.count("CONCENTRATION_UNITS MASS") == 2
    assert text.count(f"SALTVD\n     4 {salinity:g}\n     2400 {salinity:g}") == 2
    parameterize_cirrus_deck(deck, parameters(salinity))
    assert deck.read_text() == text


@pytest.mark.parametrize("brine", ["", "BRINE 0.032 MOLE\nBRINE 0.04 MASS"])
def test_missing_or_duplicate_brine_rejected_without_writing(tmp_path, brine):
    text = TEMPLATE.read_text().replace("BRINE 0.032 MOLE", brine)
    deck = tmp_path / "case.in"
    deck.write_text(text)

    with pytest.raises(ValueError, match="exactly one.*BRINE"):
        parameterize_cirrus_deck(deck, parameters(0.04))
    assert deck.read_text() == text


@pytest.mark.parametrize("salinity", [-0.01, 1.0, float("nan"), float("inf")])
def test_invalid_salinity_rejected_without_writing(tmp_path, salinity):
    text = TEMPLATE.read_text()
    deck = tmp_path / "case.in"
    deck.write_text(text)

    with pytest.raises(ValueError, match="salinity_mass_fraction must be"):
        parameterize_cirrus_deck(deck, parameters(salinity))
    assert deck.read_text() == text


def test_brine_alias_and_comments(tmp_path):
    text = TEMPLATE.read_text().replace(
        "BRINE 0.032 MOLE", "  brin 0.032 MOLE ! old value\n! BRINE 0.5 MASS"
    )
    deck = tmp_path / "case.in"
    deck.write_text(text)
    parameterize_cirrus_deck(deck, parameters(0.04))

    text = deck.read_text()
    assert re.findall(r"(?m)^\s*BRINE\s+(.+)$", text) == ["0.04 MASS"]
    assert "! BRINE 0.5 MASS" in text
