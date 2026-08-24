#!/usr/bin/env python3
"""Prepare an initialization case from a user-friendly Excel workbook.

The workbook is expected to contain:
- Header (key/value)
- GridPolicy (key/value)
- Optional well sheets (Survey, HoleCasings, Plugs, Stratigraphy, SubsurfaceAssumptions)

The script computes layer counts from thickness/target-DZ settings and stages
TEMP-0 files using the existing prepare_init_case workflow.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np
from prepare_init_case import run_initialization, stage_case

from src.GaP.libs.deck_config import CirrusDeckParameters, parameterize_cirrus_deck
from src.WellClass.libs.utils import xlsx_grid_policy, xlsx_to_well_model
from src.WellClass.libs.well_pressure.pressure_table import PressureTable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True, help="Workbook path.")
    parser.add_argument("--output-root", type=Path, required=True, help="Target case root.")
    parser.add_argument(
        "--template-root",
        type=Path,
        default=Path("test_data/examples/wildcat-pflotran"),
        help="Template case root containing model/TEMP-0.in and include/TEMP_GRD.grdecl.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite staged files if they already exist.")
    parser.add_argument(
        "--sim-command",
        type=str,
        default="",
        help="Optional external initialization command template. Use {deck} placeholder.",
    )
    parser.add_argument(
        "--write-well-json",
        action="store_true",
        help="Write parsed WellModel JSON to <output-root>/well_input.json.",
    )
    parser.add_argument("--start-date", default="2025-01-01", help="Simulation start date in ISO format.")
    parser.add_argument(
        "--simulation-years",
        type=int,
        default=100,
        help="Final simulation duration in years; used with --final-run.",
    )
    parser.add_argument(
        "--final-run",
        action="store_true",
        help="Configure the same deck for the final run and enable TEMP_LGR.grdecl.",
    )
    return parser.parse_args()


def _validated_positive(value: float, name: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _bounded_layer_count(thickness: float, target_dz: float, *, min_layers: int = 1, max_layers: int | None = None) -> int:
    _validated_positive(thickness, "thickness")
    _validated_positive(target_dz, "target_dz")
    if min_layers <= 0:
        raise ValueError("min_layers must be positive")
    if max_layers is not None and max_layers < min_layers:
        raise ValueError("max_layers must be >= min_layers")

    layers = max(min_layers, math.ceil(thickness / target_dz))
    if max_layers is not None:
        layers = min(layers, max_layers)
    return int(layers)


def _as_optional_int(policy: dict, key: str) -> int | None:
    if key not in policy:
        return None
    value = policy[key]
    if value is None or value == "":
        return None
    return int(value)


def derive_stage_args_from_policy(args: argparse.Namespace, policy: dict) -> argparse.Namespace:
    top_depth = float(policy["top_depth"])
    water_depth = float(policy["water_depth"])
    reservoir_top = float(policy["reservoir_top"])
    bottom_depth = float(policy["bottom_depth"])

    if not top_depth < water_depth < reservoir_top < bottom_depth:
        raise ValueError("GridPolicy depths must satisfy top_depth < water_depth < reservoir_top < bottom_depth")

    water_layers = _bounded_layer_count(
        water_depth - top_depth,
        float(policy["target_dz_water"]),
        min_layers=int(policy.get("min_water_layers", 1)),
        max_layers=_as_optional_int(policy, "max_water_layers"),
    )
    overburden_layers = _bounded_layer_count(
        reservoir_top - water_depth,
        float(policy["target_dz_overburden"]),
        min_layers=int(policy.get("min_overburden_layers", 1)),
        max_layers=_as_optional_int(policy, "max_overburden_layers"),
    )
    reservoir_layers = _bounded_layer_count(
        bottom_depth - reservoir_top,
        float(policy["target_dz_reservoir"]),
        min_layers=int(policy.get("min_reservoir_layers", 1)),
        max_layers=_as_optional_int(policy, "max_reservoir_layers"),
    )

    return argparse.Namespace(
        template_root=args.template_root,
        output_root=args.output_root,
        top_depth=top_depth,
        water_depth=water_depth,
        reservoir_top=reservoir_top,
        bottom_depth=bottom_depth,
        water_layers=water_layers,
        overburden_layers=overburden_layers,
        reservoir_layers=reservoir_layers,
        cells_per_layer=int(policy.get("cells_per_layer", 400)),
        force=args.force,
    )


def _add_years(start_date: date, years: int) -> date:
    if years < 0:
        raise ValueError("simulation-years must be non-negative")
    try:
        return start_date.replace(year=start_date.year + years)
    except ValueError:
        return start_date.replace(month=2, day=28, year=start_date.year + years)


def parameterize_staged_deck(args: argparse.Namespace, policy: dict, model) -> None:
    start_date = date.fromisoformat(str(policy.get("start_date", args.start_date)))
    final_date = _add_years(start_date, args.simulation_years) if args.final_run else start_date
    scenarios = model.spec.subsurface_assumptions.scenarios if model.spec.subsurface_assumptions else []
    assumptions = scenarios[0].model_dump(exclude_none=True) if scenarios else {}
    seafloor_depth = float(policy["water_depth"])
    reservoir_top = float(policy["reservoir_top"])
    overburden_datum_depth = float(assumptions.get("overburden_datum_depth", (seafloor_depth + reservoir_top) / 2))
    if not seafloor_depth < overburden_datum_depth < reservoir_top:
        raise ValueError("overburden_datum_depth must be between water_depth and reservoir_top")
    pressure_table = PressureTable(
        name="cirrus_overburden",
        depth=np.arange(0.0, overburden_datum_depth + 10.0, 10.0),
        ground_elevation=float(model.spec.well_header.ground_elevation),
        ground_temperature=float(assumptions.get("ground_temperature", 4.0)),
        geothermal_gradient=float(assumptions.get("temperature_gradient", 31.0)),
    )
    parameters = CirrusDeckParameters(
        start_date=start_date,
        final_date=final_date,
        top_depth=float(policy["top_depth"]),
        seafloor_depth=seafloor_depth,
        bottom_depth=float(policy["bottom_depth"]),
        overburden_datum_depth=overburden_datum_depth,
        overburden_pressure_bar=pressure_table.get_values_at_depth(overburden_datum_depth)["hydrostatic_pressure"],
        fluid_contact_depth=float(assumptions.get("z_fluid_contact", assumptions.get("z_resrv", 1500.0))),
        fluid_contact_pressure_bar=float(assumptions.get("p_fluid_contact", assumptions.get("p_resrv", 144.5))),
        ground_temperature_c=float(assumptions.get("ground_temperature", 4.0)),
        geothermal_gradient_c_per_km=float(assumptions.get("temperature_gradient", 31.0)),
        enable_lgr=args.final_run,
    )
    parameterize_cirrus_deck(
        args.output_root / "model" / "TEMP-0.in",
        parameters,
        grdecl_path=args.output_root / "include" / "TEMP_GRD.grdecl",
    )


def main() -> int:
    args = parse_args()

    policy = xlsx_grid_policy(args.xlsx)
    well_model = xlsx_to_well_model(args.xlsx)
    stage_args = derive_stage_args_from_policy(args, policy)
    output_deck, output_grdecl, output_tops = stage_case(stage_args)
    parameterize_staged_deck(args, policy, well_model)

    print("Staged initialization case files from workbook:")
    print(f"  deck:   {output_deck}")
    print(f"  grid:   {output_grdecl}")
    print(f"  topsdz: {output_tops}")
    print("Derived layer counts:")
    print(f"  water_layers:      {stage_args.water_layers}")
    print(f"  overburden_layers: {stage_args.overburden_layers}")
    print(f"  reservoir_layers:  {stage_args.reservoir_layers}")

    if args.write_well_json:
        output_json = args.output_root / "well_input.json"
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(well_model.model_dump(mode="json"), indent=2), encoding="utf-8")
        print(f"Wrote parsed well model JSON: {output_json}")

    if not args.sim_command:
        print("No --sim-command provided; skipping simulator execution.")
        return 0

    exit_code = run_initialization(args.sim_command, output_deck)
    if exit_code != 0:
        print(f"Initialization command failed with exit code {exit_code}.")
        return exit_code

    print("Initialization command completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
