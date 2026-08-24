#!/usr/bin/env python3
"""Generate editable Wildcat and Smeaheia workbook examples from canonical JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

EXAMPLES = {
    "wildcat": {
        "json": Path("test_data/examples/wildcat/wildcat.json"),
        "output": Path("test_data/examples/wildcat/wildcat_workbook.xlsx"),
        "grid_policy": {
            "top_depth": 4.0,
            "water_depth": 105.0,
            "reservoir_top": 2238.0,
            "bottom_depth": 3970.0,
            "target_dz_water": 50.0,
            "target_dz_overburden": 60.0,
            "target_dz_reservoir": 10.0,
            "cells_per_layer": 400,
            "min_water_layers": 1,
            "min_overburden_layers": 1,
            "min_reservoir_layers": 1,
        },
        "assumptions": {
            "temperature_gradient": 31.0,
            "ground_temperature": 4.0,
            "fluid_type": "co2",
            "z_fluid_contact": 2400.0,
            "p_fluid_contact": 245.0,
            "z_resrv": 2450.0,
            "p_resrv": 250.0,
        },
    },
    "smeaheia": {
        "json": Path("test_data/examples/smeaheia/smeaheia.json"),
        "output": Path("test_data/examples/smeaheia/smeaheia_workbook.xlsx"),
        "grid_policy": {
            "top_depth": 4.0,
            "water_depth": 312.0,
            "reservoir_top": 1214.5,
            "bottom_depth": 3162.5,
            "target_dz_water": 50.0,
            "target_dz_overburden": 60.0,
            "target_dz_reservoir": 10.0,
            "cells_per_layer": 400,
            "min_water_layers": 1,
            "min_overburden_layers": 1,
            "min_reservoir_layers": 1,
        },
        "assumptions": {
            "temperature_gradient": 31.0,
            "ground_temperature": 4.0,
            "fluid_type": "co2",
            "z_fluid_contact": 1500.0,
            "p_fluid_contact": 150.0,
            "z_resrv": 1550.0,
            "p_resrv": 155.0,
        },
    },
}


def _key_values(values: dict) -> pd.DataFrame:
    return pd.DataFrame({"key": list(values), "value": list(values.values())})


def create_workbook(example: dict) -> Path:
    source = example["json"]
    output = example["output"]
    payload = json.loads(source.read_text(encoding="utf-8"))
    spec = payload["spec"]
    output.parent.mkdir(parents=True, exist_ok=True)

    notes = pd.DataFrame(
        {
            "note": [
                "Physical well sheets are copied from the canonical JSON fixture.",
                "GridPolicy and SubsurfaceAssumptions are editable example scenario values and must be reviewed for a real case.",
                "z_fluid_contact and p_fluid_contact define the GAS_WATER datum and WGC depth in CIRRUS.",
            ]
        }
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _key_values(payload.get("metadata", {})).to_excel(writer, sheet_name="Metadata", index=False)
        _key_values(spec["well_header"]).to_excel(writer, sheet_name="Header", index=False)
        _key_values(example["grid_policy"]).to_excel(writer, sheet_name="GridPolicy", index=False)
        pd.DataFrame(spec.get("hole_casings", [])).to_excel(writer, sheet_name="HoleCasings", index=False)
        pd.DataFrame(spec.get("plugs", [])).to_excel(writer, sheet_name="Plugs", index=False)
        pd.DataFrame(spec.get("stratigraphy", [])).to_excel(writer, sheet_name="Stratigraphy", index=False)
        pd.DataFrame([example["assumptions"]]).to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)
        notes.to_excel(writer, sheet_name="Notes", index=False)
    return output


def main() -> int:
    for name, example in EXAMPLES.items():
        print(f"Created {name} workbook: {create_workbook(example)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
