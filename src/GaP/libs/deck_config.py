from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class CirrusDeckParameters:
    """Values used to configure one CIRRUS deck for either run stage."""

    start_date: date
    final_date: date
    top_depth: float
    seafloor_depth: float
    bottom_depth: float
    overburden_datum_depth: float
    overburden_pressure_bar: float
    fluid_contact_depth: float
    fluid_contact_pressure_bar: float
    ground_temperature_c: float = 4.0
    geothermal_gradient_c_per_km: float = 31.0
    enable_lgr: bool = False


def _date_text(value: date) -> str:
    return value.strftime("%-d %b %Y").upper()


def _replace_line(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^\s*{re.escape(key)}\s+.*$"
    replacement = f" {key}  {value}"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"deck is missing {key}")
    return updated


def format_rtempvd(
    *,
    top_depth: float,
    seafloor_depth: float,
    bottom_depth: float,
    ground_temperature_c: float = 4.0,
    geothermal_gradient_c_per_km: float = 31.0,
) -> str:
    """Create a minimum three-point constant-then-geothermal temperature table."""

    if not top_depth <= seafloor_depth < bottom_depth:
        raise ValueError("temperature depths must satisfy top <= seafloor < bottom")
    middle_depth = seafloor_depth + (bottom_depth - seafloor_depth) / 2

    def temperature(depth: float) -> float:
        if depth <= seafloor_depth:
            return ground_temperature_c
        return ground_temperature_c + (depth - seafloor_depth) * geothermal_gradient_c_per_km / 1000

    points = [
        (top_depth, temperature(top_depth)),
        (seafloor_depth, ground_temperature_c),
        (middle_depth, temperature(middle_depth)),
        (bottom_depth, temperature(bottom_depth)),
    ]
    return "\n".join(f"     {depth:g}    {value:g}" for depth, value in points)


def format_saltvd(*, top_depth: float, bottom_depth: float, concentration_mole: float = 0.032) -> str:
    """Create a constant-salinity table spanning the required equilibration depth."""

    if not top_depth < bottom_depth:
        raise ValueError("salt-table depths must satisfy top < bottom")
    return f"     {top_depth:g} {concentration_mole:g}\n     {bottom_depth:g} {concentration_mole:g}"


def _replace_co2_equilibration(text: str, parameters: CirrusDeckParameters) -> str:
    block_pattern = r"(?ms)(^EQUILIBRATION CO2_column\s*\n)(.*?)(^/\s*$)"
    match = re.search(block_pattern, text)
    if match is None:
        raise ValueError("deck is missing EQUILIBRATION CO2_column")

    block = match.group(2)
    block = _replace_line(block, "DATUM_D", f"{parameters.fluid_contact_depth:g} m")
    block = _replace_line(block, "PRESSURE", f"{parameters.fluid_contact_pressure_bar:g} Bar")
    block = _replace_line(block, "WGC_D", f"{parameters.fluid_contact_depth:g} m")
    temperature_bottom = max(parameters.bottom_depth, parameters.fluid_contact_depth)
    table = format_rtempvd(
        top_depth=parameters.top_depth,
        seafloor_depth=parameters.seafloor_depth,
        bottom_depth=temperature_bottom,
        ground_temperature_c=parameters.ground_temperature_c,
        geothermal_gradient_c_per_km=parameters.geothermal_gradient_c_per_km,
    )
    block, count = re.subn(
        r"(?ms)(^\s*RTEMPVD\s*\n).*?^(\s*/\s*$)",
        lambda match: f"{match.group(1)}{table}\n{match.group(2)}",
        block,
        count=1,
    )
    if count != 1:
        raise ValueError("CO2 equilibration is missing RTEMPVD")
    return text[: match.start(2)] + block + text[match.end(2) :]


def _replace_overburden_equilibration(text: str, parameters: CirrusDeckParameters) -> str:
    block_pattern = r"(?ms)(^EQUILIBRATION overburden_water\s*\n)(.*?)(^/\s*$)"
    match = re.search(block_pattern, text)
    if match is None:
        raise ValueError("deck is missing EQUILIBRATION overburden_water")

    block = match.group(2)
    block = _replace_line(block, "DATUM_D", f"{parameters.overburden_datum_depth:g} m")
    block = _replace_line(block, "PRESSURE", f"{parameters.overburden_pressure_bar:g} Bar")
    return text[: match.start(2)] + block + text[match.end(2) :]


def _replace_salt_tables(text: str, *, top_depth: float, bottom_depth: float) -> str:
    salt_table = format_saltvd(top_depth=top_depth, bottom_depth=bottom_depth)
    updated, count = re.subn(
        r"(?ms)(^\s*SALTVD\s*\n).*?^(\s*/\s*$)",
        lambda match: f"{match.group(1)}{salt_table}\n{match.group(2)}",
        text,
    )
    if count == 0:
        raise ValueError("deck is missing SALTVD")
    return updated


def _remove_unused_wells_section(text: str) -> str:
    pattern = r"(?ms)^#=+ Wells =+\n.*?(?=^#=+\n)"
    return re.sub(pattern, "", text, count=1)


def _set_lgr_include(grdecl_path: Path, enabled: bool) -> None:
    text = grdecl_path.read_text(encoding="utf-8")
    lgr_line = "external_file ../include/TEMP_LGR.grdecl /"
    lines = [line for line in text.splitlines() if line.strip() != lgr_line]
    if enabled:
        try:
            index = next(index for index, line in enumerate(lines) if "external_file ../include/tops_dz.inc" in line)
        except StopIteration as exc:
            raise ValueError("grid deck is missing tops_dz include") from exc
        lines.insert(index, lgr_line)
    grdecl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parameterize_cirrus_deck(deck_path: str | Path, parameters: CirrusDeckParameters, *, grdecl_path: str | Path | None = None) -> Path:
    """Apply workbook/WellClass values to a CIRRUS deck in place."""

    deck_path = Path(deck_path)
    text = deck_path.read_text(encoding="utf-8")
    text = _replace_line(text, "START_DATE", _date_text(parameters.start_date))
    text = _replace_line(text, "FINAL_DATE", _date_text(parameters.final_date))
    text = _replace_overburden_equilibration(text, parameters)
    text = _replace_co2_equilibration(text, parameters)
    text = _replace_salt_tables(
        text,
        top_depth=parameters.top_depth,
        bottom_depth=max(parameters.bottom_depth, parameters.fluid_contact_depth),
    )
    text = _remove_unused_wells_section(text)
    deck_path.write_text(text, encoding="utf-8")

    if grdecl_path is not None:
        _set_lgr_include(Path(grdecl_path), parameters.enable_lgr)
    return deck_path
