#!/usr/bin/env python3
"""Build a GaP LGR/CARFIN GRDECL from WellClass JSON and EGRID/INIT files."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.GaP.libs.grid_utils.lgr_equilibration import restrict_co2_equilibration
from src.WellClass.libs.grid_utils import LGRBuilder, WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--well-json", type=Path, required=True, help="WellClass JSON input.")
    parser.add_argument(
        "--sim-case",
        type=Path,
        required=True,
        help="Simulator case prefix, without .EGRID or .INIT, such as case/model/TEMP-0.",
    )
    parser.add_argument("--output-folder", type=Path, required=True, help="Folder for the generated LGR GRDECL.")
    parser.add_argument("--lgr-name", default="TEMP_LGR", help="Generated LGR name and file stem.")
    parser.add_argument("--oh-perm", type=float, default=10000.0, help="Open-hole permeability default.")
    parser.add_argument("--cb-perm", type=float, default=0.05, help="Cement-bond permeability default.")
    parser.add_argument("--barrier-perm", type=float, default=0.05, help="Barrier permeability default.")
    parser.add_argument("--ali-way", action="store_true", help="Use the legacy Ali refinement mode.")
    return parser.parse_args()


def build_lgr(args: argparse.Namespace) -> Path:
    processed_well = WellProcessed.from_json(args.well_json)
    well_frames = WellDataFrame(
        processed_well,
        oh_perm=args.oh_perm,
        cb_perm=args.cb_perm,
        barrier_perm=args.barrier_perm,
    )
    builder = LGRBuilder(str(args.sim_case), well_frames.annulus_df, well_frames.holes_df, args.ali_way)
    builder.build_grdecl(
        str(args.output_folder),
        args.lgr_name,
        well_frames.holes_df,
        well_frames.casings_df,
        well_frames.barrier_regions_df,
    )
    lgr_path = args.output_folder / f"{args.lgr_name}.grdecl"
    reservoir_tops = [record["tvd_msl_top"] for record in processed_well.stratigraphy or [] if record.get("unit_type") == "reservoir"]
    qualifying_plugs = [
        record for record in processed_well.processed_plugs or [] if reservoir_tops and record["bottom_tvd_msl"] < min(reservoir_tops)
    ]
    if qualifying_plugs:
        deepest_plug = max(qualifying_plugs, key=lambda record: record["bottom_tvd_msl"])
        plug_row = well_frames.barrier_regions_df[well_frames.barrier_regions_df["barrier_name"] == deepest_plug["name"]].iloc[0]
        restrict_co2_equilibration(lgr_path, first_co2_layer=int(plug_row["k_max"]) + 2)
    return lgr_path


def main() -> int:
    args = parse_args()
    output_path = build_lgr(args)
    print(f"Generated LGR GRDECL: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
