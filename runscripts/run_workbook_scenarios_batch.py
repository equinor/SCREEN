#!/usr/bin/env python3
"""Run multiple simulation scenarios from a workbook and collect results.

Executes the workbook -> CIRRUS initialization -> GaP LGR workflow for each
DesignMatrix case. Each case gets a deterministic stem derived from the
workbook well name and case name (see src/GaP/libs/case_naming.py), used for
its directory and generated files.

Output structure:
  <output-root>/
    batch_manifest.json
    <well>_<case_name_1>/
      model/<well>_<case_name_1>.in
      include/<well>_<case_name_1>_GRD.grdecl, <well>_<case_name_1>_LGR.grdecl
      logs/
      scenario.json
      well_input.json
    <well>_<case_name_2>/
    ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.GaP.libs.case_naming import resolve_case_stems, well_label
from src.WellClass.libs.utils import xlsx_to_simulation_design, xlsx_to_well_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True, help="Workbook input deck.")
    parser.add_argument("--output-root", type=Path, required=True, help="Batch output directory (per-case subdirs created).")
    parser.add_argument("--template-root", type=Path, default=Path("test_data/examples/wildcat-pflotran"))
    parser.add_argument("--sim-command", required=True, help="CIRRUS initialization command template using {deck}.")
    parser.add_argument("--queue-poll-interval", type=float, default=15.0, help="Seconds between LSF job status checks.")
    parser.add_argument("--queue-timeout", type=float, default=86400.0, help="Maximum seconds to wait for an LSF job.")
    parser.add_argument("--run-final", action="store_true", help="Run CIRRUS again after the LGR is generated.")
    parser.add_argument("--simulation-years", type=int, default=100, help="Final duration in years.")
    parser.add_argument("--start-date", default="2025-01-01", help="Simulation start date in ISO format.")
    parser.add_argument("--lgr-name", default="TEMP_LGR", help="CARFIN LGR name inside each generated LGR file.")
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
        help="Maximum number of scenarios to run concurrently.",
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
        "--queue-poll-interval",
        str(getattr(args, "queue_poll_interval", 15.0)),
        "--queue-timeout",
        str(getattr(args, "queue_timeout", 86400.0)),
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


def case_stems(design, xlsx_file: Path) -> dict[str, str]:
    """Map each case name to its directory and file stem."""
    names = [scenario.case_name for scenario in design.scenarios]
    return dict(zip(names, resolve_case_stems(well_label(xlsx_to_well_model(xlsx_file)), names)))


def write_batch_manifest(design, args: argparse.Namespace, failed_cases: list[str]) -> Path:
    stems = case_stems(design, args.xlsx)
    manifest = {
        "workbook": str(args.xlsx),
        "template_root": str(args.template_root),
        "cases": [
            {
                "case_index": index,
                "case_name": scenario.case_name,
                "case_stem": stems[scenario.case_name],
                "case_dir": stems[scenario.case_name],
                "status": "failed" if scenario.case_name in failed_cases else "succeeded",
            }
            for index, scenario in enumerate(design.scenarios, 1)
        ],
    }
    path = args.output_root / "batch_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def run_scenarios(design, args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Run scenario cases concurrently and return successful and failed names."""

    successful_cases = []
    failed_cases = []
    futures = {}
    stems = case_stems(design, args.xlsx)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        for scenario in design.scenarios:
            case_name = scenario.case_name
            case_output_root = args.output_root / stems[case_name]
            future = executor.submit(
                run_scenario_case,
                args.xlsx,
                case_name,
                case_output_root,
                args.template_root,
                args.sim_command,
                args,
            )
            futures[future] = case_name

        for future in as_completed(futures):
            case_name = futures[future]
            try:
                exit_code = future.result()
            except Exception as exc:  # pragma: no cover - defensive worker boundary
                print(f"Scenario '{case_name}' raised an exception: {exc}")
                exit_code = 1

            if exit_code != 0:
                failed_cases.append(case_name)
                print(f"❌ Scenario '{case_name}' failed with exit code {exit_code}")
            else:
                successful_cases.append(case_name)
                print(f"✅ Scenario '{case_name}' completed successfully")

    return successful_cases, failed_cases


def main() -> int:
    args = parse_args()

    if args.jobs < 1:
        print("Error: --jobs must be at least 1.")
        return 2

    args.output_root.mkdir(parents=True, exist_ok=True)

    try:
        design = xlsx_to_simulation_design(args.xlsx)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    if not design.scenarios:
        print("Error: No cases found in workbook DesignMatrix or legacy SubsurfaceAssumptions sheet.")
        return 1

    scenario_names = [scenario.case_name for scenario in design.scenarios]
    print(f"Found {len(scenario_names)} scenario(s): {', '.join(scenario_names)}")

    successful_cases, failed_cases = run_scenarios(design, args)
    manifest_path = write_batch_manifest(design, args, failed_cases)
    stems = case_stems(design, args.xlsx)

    print(f"\n{'='*70}")
    print("Batch execution summary:")
    print(f"  Total scenarios: {len(scenario_names)}")
    print(f"  Successful: {len(successful_cases)}")
    print(f"  Failed: {len(failed_cases)}")
    print(f"  Manifest: {manifest_path}")

    if successful_cases:
        print("\n  Successful cases:")
        for case_name in successful_cases:
            case_root = args.output_root / stems[case_name]
            print(f"    - {case_name}: {case_root}")

    if failed_cases:
        print("\n  Failed cases:")
        for case_name in failed_cases:
            case_root = args.output_root / stems[case_name]
            print(f"    - {case_name}: {case_root}")
        print(f"{'='*70}")
        return 1

    print(f"{'='*70}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
