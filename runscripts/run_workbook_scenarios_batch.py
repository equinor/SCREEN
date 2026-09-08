#!/usr/bin/env python3
"""Run multiple simulation scenarios from a workbook and collect results.

Executes the workbook -> CIRRUS initialization -> GaP LGR workflow for each
scenario in the SubsurfaceAssumptions sheet, organizing outputs by case_name.

Output structure:
  <output-root>/
    <case_name_1>/
      model/
      include/
      well_input.json
    <case_name_2>/
      model/
      include/
      well_input.json
    ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.WellClass.libs.utils import xlsx_to_simulation_design


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True, help="Workbook input deck.")
    parser.add_argument("--output-root", type=Path, required=True, help="Batch output directory (per-case subdirs created).")
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
    parser.add_argument("--plot", action="store_true", help="Save a sketch and pressure QC plot for each scenario.")
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel scenarios (currently sequential only; reserved for future use).",
    )
    return parser.parse_args()


def run_scenario_case(
    xlsx_file: Path,
    case_name: str,
    case_output_root: Path,
    template_root: Path,
    sim_command: str,
    args: argparse.Namespace,
) -> int:
    """Execute the workflow for a single scenario case."""

    command = [
        sys.executable,
        "runscripts/run_workbook_to_cirrus_lgr.py",
        "--xlsx",
        str(xlsx_file),
        "--output-root",
        str(case_output_root),
        "--template-root",
        str(template_root),
        "--sim-command",
        sim_command,
        "--case-name",
        case_name,
        "--simulation-years",
        str(args.simulation_years),
        "--start-date",
        args.start_date,
        "--lgr-name",
        args.lgr_name,
        "--oh-perm",
        str(args.oh_perm),
        "--cb-perm",
        str(args.cb_perm),
        "--barrier-perm",
        str(args.barrier_perm),
    ]

    if args.run_final:
        command.append("--run-final")
    if args.ali_way:
        command.append("--ali-way")
    if args.force:
        command.append("--force")
    if args.plot:
        command.append("--plot")

    print(f"\n{'='*70}")
    print(f"Running scenario: {case_name}")
    print(f"Output directory: {case_output_root}")
    print(f"{'='*70}")

    result = subprocess.run(command, cwd=Path(__file__).parent.parent)
    return result.returncode


def main() -> int:
    args = parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)

    try:
        design = xlsx_to_simulation_design(args.xlsx)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    if not design.scenarios:
        print("Error: No scenarios found in workbook SubsurfaceAssumptions sheet.")
        return 1

    scenario_names = [scenario.case_name for scenario in design.scenarios]
    print(f"Found {len(scenario_names)} scenario(s): {', '.join(scenario_names)}")

    failed_cases = []
    successful_cases = []

    for scenario in design.scenarios:
        case_name = scenario.case_name
        case_output_root = args.output_root / case_name
        exit_code = run_scenario_case(
            args.xlsx,
            case_name,
            case_output_root,
            args.template_root,
            args.sim_command,
            args,
        )

        if exit_code != 0:
            failed_cases.append(case_name)
            print(f"❌ Scenario '{case_name}' failed with exit code {exit_code}")
        else:
            successful_cases.append(case_name)
            print(f"✅ Scenario '{case_name}' completed successfully")

    print(f"\n{'='*70}")
    print("Batch execution summary:")
    print(f"  Total scenarios: {len(scenario_names)}")
    print(f"  Successful: {len(successful_cases)}")
    print(f"  Failed: {len(failed_cases)}")

    if successful_cases:
        print("\n  Successful cases:")
        for case_name in successful_cases:
            case_root = args.output_root / case_name
            print(f"    - {case_name}: {case_root}")

    if failed_cases:
        print("\n  Failed cases:")
        for case_name in failed_cases:
            case_root = args.output_root / case_name
            print(f"    - {case_name}: {case_root}")
        print(f"{'='*70}")
        return 1

    print(f"{'='*70}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
