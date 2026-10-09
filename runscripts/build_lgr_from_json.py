#!/usr/bin/env python3
"""Build a GaP LGR/CARFIN GRDECL from WellClass JSON and EGRID/INIT files."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from math import pi
from pathlib import Path

from src.GaP.libs.grid_utils.lgr_equilibration import restrict_co2_equilibration
from src.GaP.libs.models.simulation_scenario import SimulationScenario
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
    parser.add_argument("--lgr-name", default="TEMP_LGR", help="CARFIN LGR name; also the file stem unless --lgr-file-stem is set.")
    parser.add_argument("--lgr-file-stem", default=None, help="Generated LGR GRDECL file stem.")
    parser.add_argument("--oh-perm", type=float, default=10000.0, help="Open-hole permeability default in mD.")
    parser.add_argument("--cb-perm", type=float, default=0.05, help="Cement-bond permeability default in mD.")
    parser.add_argument("--barrier-perm", type=float, default=0.05, help="Barrier permeability default in mD.")
    parser.add_argument("--ali-way", action="store_true", help="Use the legacy Ali refinement mode.")
    parser.add_argument("--casing-hole-casing", help="Experimental hole: exact casing name (not casing cement).")
    parser.add_argument("--casing-hole-depth-mTVDMSL", type=float, help="Experimental hole depth in m TVDMSL.")
    parser.add_argument("--casing-hole-diameter-m", type=float, help="Experimental circular hole diameter in m.")
    return parser.parse_args()


def build_lgr(args: argparse.Namespace) -> Path:
    hole = SimulationScenario(
        casing_hole_casing=getattr(args, "casing_hole_casing", None),
        casing_hole_depth_mTVDMSL=getattr(args, "casing_hole_depth_mTVDMSL", None),
        casing_hole_diameter_m=getattr(args, "casing_hole_diameter_m", None),
    ).casing_hole
    processed_well = WellProcessed.from_json(args.well_json)
    if hole is not None:
        hole.validate_casing(
            (record["name"], float(record["tvd_msl_top"]), float(record["tvd_msl_bottom"]))
            for record in processed_well.hole_casings or []
            if record["type"] == "casing"
        )
    well_frames = WellDataFrame(
        processed_well,
        oh_perm=args.oh_perm,
        cb_perm=args.cb_perm,
        barrier_perm=args.barrier_perm,
        permeability_overrides=getattr(args, "permeability_overrides", None),
        interval_permeability_overrides=getattr(args, "interval_permeability_overrides", None),
    )
    builder = LGRBuilder(str(args.sim_case), well_frames.annulus_df, well_frames.holes_df, args.ali_way)
    builder.build_grdecl(
        str(args.output_folder),
        args.lgr_name,
        well_frames.holes_df,
        well_frames.casings_df,
        well_frames.barrier_regions_df,
        casing_hole=hole,
    )
    lgr_path = args.output_folder / f"{args.lgr_name}.grdecl"
    lgr_file_stem = getattr(args, "lgr_file_stem", None)
    if lgr_file_stem and lgr_file_stem != args.lgr_name:
        lgr_path = lgr_path.replace(args.output_folder / f"{lgr_file_stem}.grdecl")
    reservoir_tops = [record["tvd_msl_top"] for record in processed_well.stratigraphy or [] if record.get("unit_type") == "reservoir"]
    qualifying_plugs = [
        record for record in processed_well.processed_plugs or [] if reservoir_tops and record["bottom_tvd_msl"] < min(reservoir_tops)
    ]
    if qualifying_plugs:
        deepest_plug = max(qualifying_plugs, key=lambda record: record["bottom_tvd_msl"])
        plug_row = well_frames.barrier_regions_df[well_frames.barrier_regions_df["barrier_name"] == deepest_plug["name"]].iloc[0]
        restrict_co2_equilibration(lgr_path, first_co2_layer=int(plug_row["k_max"]) + 2)
    if hole is not None:
        report = {
            "experimental": True,
            "input": hole.model_dump(mode="json"),
            "side": "+X",
            "placement": "diameter span centered on side midpoint; faces ordered by increasing J",
            "allocation": "circular area weighted by lateral span overlap",
            "indexing": "one-based LGR cells; MULTX is the positive-X face",
            "requested_area_m2": pi * (hole.diameter_m / 2) ** 2,
            "allocated_area_m2": sum(face.opening_area_m2 for face in builder.casing_hole_faces),
            "area_relative_tolerance": 1e-12,
            "faces": [asdict(face) for face in builder.casing_hole_faces],
        }
        lgr_path.with_suffix(".casing_hole.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        lgr_path.with_suffix(".casing_hole.json").unlink(missing_ok=True)
    return lgr_path


def main() -> int:
    args = parse_args()
    output_path = build_lgr(args)
    print(f"Generated LGR GRDECL: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
