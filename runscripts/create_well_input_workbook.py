#!/usr/bin/env python3
"""Create a starter Excel workbook for SCREEN preprocessing inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Path to output .xlsx file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    metadata = pd.DataFrame(
        {
            "key": ["namespace", "name", "author"],
            "value": ["screen", "example-case", "user"],
        }
    )
    header = pd.DataFrame(
        {
            "key": [
                "unique_wellbore_identifier",
                "depth_reference_rkb",
                "depth_reference_rkb_unit",
                "ground_elevation",
                "ground_elevation_unit",
                "total_depth_rkb",
                "total_depth_rkb_unit",
            ],
            "value": ["NO 00/0-0", 27, "m", 105, "m", 3997, "m"],
        }
    )
    grid_policy = pd.DataFrame(
        {
            "key": [
                "top_depth",
                "water_depth",
                "reservoir_top",
                "bottom_depth",
                "target_dz_water",
                "target_dz_overburden",
                "target_dz_reservoir",
                "cells_per_layer",
                "min_water_layers",
                "min_overburden_layers",
                "min_reservoir_layers",
            ],
            "value": [4.0, 104.0, 1004.0, 1504.0, 50.0, 60.0, 8.0, 400, 1, 1, 1],
        }
    )
    survey = pd.DataFrame(
        {
            "md_rkb": [0.0, 1000.0, 2000.0],
            "inclination_deg": [0.0, 0.0, 0.0],
            "azimuth_deg": [0.0, 0.0, 0.0],
        }
    )
    hole_casings = pd.DataFrame(
        {
            "name": ["Hole 17 1/2 in", "Casing 13 3/8 in", "Cement 13 3/8 in"],
            "type": ["hole", "casing", "casing cement"],
            "top_rkb": [444, 450, 450],
            "bottom_rkb": [1812, 1803, 1803],
            "diameter_in": ["17 1/2", "13 3/8", "13 3/8"],
            "shoe": [False, True, False],
            "hc_perm": [None, 500.0, 500.0],
        }
    )
    stratigraphy = pd.DataFrame(
        {
            "name": ["OVERBURDEN", "RESERVOIR"],
            "top_rkb": [132, 2265],
            "bottom_rkb": [2265, 2532],
            "unit_type": ["undefined", "reservoir"],
            "unit_perm": [None, None],
        }
    )
    assumptions = pd.DataFrame(
        {
            "temperature_gradient": [31.0],
            "ground_temperature": [4.0],
            "fluid_type": ["co2"],
            "z_fluid_contact": [2400.0],
            "p_fluid_contact": [245.0],
            "z_resrv": [2450.0],
            "p_resrv": [250.0],
        }
    )

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        header.to_excel(writer, sheet_name="Header", index=False)
        grid_policy.to_excel(writer, sheet_name="GridPolicy", index=False)
        survey.to_excel(writer, sheet_name="Survey", index=False)
        hole_casings.to_excel(writer, sheet_name="HoleCasings", index=False)
        stratigraphy.to_excel(writer, sheet_name="Stratigraphy", index=False)
        assumptions.to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)

    print(f"Created workbook template: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
