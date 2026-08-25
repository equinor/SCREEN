from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..models.well_model import WellModel


def _read_sheet(workbook: Path, sheet_name: str) -> pd.DataFrame | None:
    try:
        return pd.read_excel(workbook, sheet_name=sheet_name, engine="openpyxl")
    except ValueError:
        return None


def _key_value_sheet(df: pd.DataFrame, *, sheet_name: str) -> dict[str, Any]:
    if df is None:
        return {}
    columns = [str(col).strip().lower() for col in df.columns]
    if columns != ["key", "value"]:
        raise ValueError(f"sheet '{sheet_name}' must have columns ['key', 'value']")
    cleaned = df.dropna(how="all")
    payload: dict[str, Any] = {}
    for _, row in cleaned.iterrows():
        key = row["key"]
        value = row["value"]
        if pd.isna(key):
            continue
        payload[str(key).strip()] = value
    return payload


def _records_sheet(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None:
        return []
    cleaned = df.dropna(how="all")
    if cleaned.empty:
        return []
    records = cleaned.to_dict(orient="records")
    filtered: list[dict[str, Any]] = []
    for record in records:
        item = {str(k): v for k, v in record.items() if not pd.isna(v)}
        if item:
            filtered.append(item)
    return filtered


def xlsx_to_well_model(xlsx_file: str | Path) -> WellModel:
    """Parse a user workbook into the canonical WellModel."""

    workbook = Path(xlsx_file)
    if not workbook.exists():
        raise FileNotFoundError(f"workbook not found: {workbook}")

    header_sheet = _read_sheet(workbook, "Header")
    if header_sheet is None:
        raise ValueError("missing required sheet: Header")

    metadata_sheet = _read_sheet(workbook, "Metadata")
    survey_sheet = _read_sheet(workbook, "Survey")
    hole_casings_sheet = _read_sheet(workbook, "HoleCasings")
    plugs_sheet = _read_sheet(workbook, "Plugs")
    stratigraphy_sheet = _read_sheet(workbook, "Stratigraphy")
    assumptions_sheet = _read_sheet(workbook, "SubsurfaceAssumptions")

    metadata = _key_value_sheet(metadata_sheet, sheet_name="Metadata") if metadata_sheet is not None else {}
    header = _key_value_sheet(header_sheet, sheet_name="Header")

    spec: dict[str, Any] = {
        "well_header": header,
    }

    if survey_sheet is not None:
        survey_records = _records_sheet(survey_sheet)
        if survey_records:
            spec["well_survey"] = {
                "md_rkb": [record["md_rkb"] for record in survey_records],
                "inclination_deg": [record["inclination_deg"] for record in survey_records],
                "azimuth_deg": [record["azimuth_deg"] for record in survey_records],
            }

    hole_casings = _records_sheet(hole_casings_sheet)
    if hole_casings:
        spec["hole_casings"] = hole_casings

    plugs = _records_sheet(plugs_sheet)
    if plugs:
        spec["plugs"] = plugs

    stratigraphy = _records_sheet(stratigraphy_sheet)
    if stratigraphy:
        spec["stratigraphy"] = stratigraphy

    assumptions = _records_sheet(assumptions_sheet)
    if assumptions:
        spec["subsurface_assumptions"] = {"scenarios": assumptions}

    payload: dict[str, Any] = {
        "apiVersion": "well/v0.1",
        "kind": "Well",
        "spec": spec,
    }

    if metadata:
        payload["metadata"] = metadata

    return WellModel(**payload)


def xlsx_grid_policy(xlsx_file: str | Path) -> dict[str, Any]:
    """Parse grid-policy settings for initialization staging.

    Required keys in the GridPolicy sheet:
    - top_depth
    - water_depth
    - reservoir_top
    - bottom_depth
    - target_dz_water
    - target_dz_overburden
    - target_dz_reservoir

    Optional keys:
    - cells_per_layer (default 400)
    - min_water_layers (default 1)
    - min_overburden_layers (default 1)
    - min_reservoir_layers (default 1)
    - max_water_layers
    - max_overburden_layers
    - max_reservoir_layers
    - nx, ny (default 20)
    - dx, dy (default 200 m)
    - reservoir_permx (default 0.01)
    - aquifer_layers (default 3)
    - porv_multiplier (default 2000)
    - permz_multiplier (default 0.1)
    """

    workbook = Path(xlsx_file)
    if not workbook.exists():
        raise FileNotFoundError(f"workbook not found: {workbook}")

    policy_sheet = _read_sheet(workbook, "GridPolicy")
    if policy_sheet is None:
        raise ValueError("missing required sheet: GridPolicy")

    policy = _key_value_sheet(policy_sheet, sheet_name="GridPolicy")
    required = {
        "top_depth",
        "water_depth",
        "reservoir_top",
        "bottom_depth",
        "target_dz_water",
        "target_dz_overburden",
        "target_dz_reservoir",
    }
    missing = sorted(required - set(policy.keys()))
    if missing:
        raise ValueError(f"GridPolicy is missing required keys: {', '.join(missing)}")

    return policy
