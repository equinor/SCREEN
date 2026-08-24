#!/usr/bin/env python3
"""Run the workbook -> CIRRUS initialization -> GaP LGR workflow."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

from build_lgr_from_json import build_lgr
from prepare_init_case import stage_case
from prepare_init_case_from_xlsx import derive_stage_args_from_policy, parameterize_staged_deck

from src.WellClass.libs.utils import xlsx_grid_policy, xlsx_to_well_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True, help="Workbook input deck.")
    parser.add_argument("--output-root", type=Path, required=True, help="Case output directory.")
    parser.add_argument("--template-root", type=Path, default=Path("test_data/examples/wildcat-pflotran"))
    parser.add_argument("--sim-command", required=True, help="CIRRUS initialization command template using {deck}.")
    parser.add_argument("--run-final", action="store_true", help="Run CIRRUS again after the LGR is generated.")
    parser.add_argument("--simulation-years", type=int, default=100, help="Final duration in years.")
    parser.add_argument("--start-date", default="2025-01-01", help="Simulation start date in ISO format.")
    parser.add_argument("--lgr-name", default="TEMP_LGR", help="Generated LGR file stem.")
    parser.add_argument("--oh-perm", type=float, default=10000.0)
    parser.add_argument("--cb-perm", type=float, default=0.05)
    parser.add_argument("--barrier-perm", type=float, default=0.05)
    parser.add_argument("--ali-way", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def run_simulator(command_template: str, deck_path: Path) -> None:
    deck_path = deck_path.resolve()
    command = command_template.format(deck=shlex.quote(str(deck_path)))
    result = subprocess.run(command, shell=True, cwd=deck_path.parent, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"CIRRUS command failed with exit code {result.returncode}")


def find_simulator_case(output_root: Path, deck_path: Path) -> Path:
    prefix = deck_path.with_suffix("")
    candidates = (prefix, output_root / "model" / "TEMP-0", output_root / "TEMP-0")
    for candidate in candidates:
        if candidate.with_suffix(".EGRID").exists() and candidate.with_suffix(".INIT").exists():
            return candidate
    raise FileNotFoundError(
        f"CIRRUS did not produce both .EGRID and .INIT for {deck_path}; searched: " + ", ".join(str(candidate) for candidate in candidates)
    )


def run_workflow(args: argparse.Namespace) -> Path:
    policy = xlsx_grid_policy(args.xlsx)
    model = xlsx_to_well_model(args.xlsx)
    stage_args = derive_stage_args_from_policy(args, policy)
    deck_path, grdecl_path, _ = stage_case(stage_args)

    args.final_run = False
    parameterize_staged_deck(args, policy, model)
    output_json = args.output_root / "well_input.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(model.model_dump(mode="json"), indent=2), encoding="utf-8")

    print(f"Running CIRRUS initialization: {deck_path}")
    run_simulator(args.sim_command, deck_path)
    sim_case = find_simulator_case(args.output_root, deck_path)

    lgr_args = argparse.Namespace(
        well_json=output_json,
        sim_case=sim_case,
        output_folder=args.output_root / "include",
        lgr_name=args.lgr_name,
        oh_perm=args.oh_perm,
        cb_perm=args.cb_perm,
        barrier_perm=args.barrier_perm,
        ali_way=args.ali_way,
    )
    lgr_path = build_lgr(lgr_args)

    args.final_run = True
    parameterize_staged_deck(args, policy, model)
    print(f"Generated LGR: {lgr_path}")
    if args.run_final:
        print(f"Running final CIRRUS simulation: {deck_path}")
        run_simulator(args.sim_command, deck_path)
    else:
        print("Final CIRRUS run not requested; deck is configured and ready.")
    return lgr_path


def main() -> int:
    run_workflow(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
