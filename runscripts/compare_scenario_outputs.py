#!/usr/bin/env python3
"""Compare static and dynamic outputs from a scenario batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase

STATIC_FILES = (
    Path("include/TEMP_GRD.grdecl"),
    Path("include/TEMP_LGR.grdecl"),
    Path("model/TEMP-0.EGRID"),
    Path("model/TEMP-0.INIT"),
)
DYNAMIC_KEYWORDS = ("PRESSURE", "SWAT", "SGAS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--baseline", help="Baseline scenario directory name; defaults to the first sorted case.")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scenario_payload(case_root: Path) -> dict[str, object]:
    path = case_root / "scenario.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def compare_case(baseline_root: Path, case_root: Path) -> dict[str, object]:
    static = {}
    for relative_path in STATIC_FILES:
        baseline_path = baseline_root / relative_path
        case_path = case_root / relative_path
        static[str(relative_path)] = {
            "equal": baseline_path.is_file() and case_path.is_file() and sha256(baseline_path) == sha256(case_path),
            "baseline_sha256": sha256(baseline_path) if baseline_path.is_file() else None,
            "case_sha256": sha256(case_path) if case_path.is_file() else None,
        }

    baseline = scenario_payload(baseline_root)
    case = scenario_payload(case_root)
    changed_fields = sorted(key for key in set(baseline) | set(case) if baseline.get(key) != case.get(key))
    dynamic: dict[str, object] = {}
    baseline_case = ResdataCase(baseline_root / "model" / "TEMP-0")
    case_data = ResdataCase(case_root / "model" / "TEMP-0")
    common_keywords = [keyword for keyword in DYNAMIC_KEYWORDS if keyword in baseline_case.restart_keywords and keyword in case_data.restart_keywords]
    common_timesteps = min(len(baseline_case.restart_timesteps), len(case_data.restart_timesteps))
    for keyword in common_keywords:
        differences = []
        for timestep in range(common_timesteps):
            left = baseline_case.restart_lgr_vector(keyword, timestep)
            right = case_data.restart_lgr_vector(keyword, timestep)
            differences.append(
                {
                    "timestep": timestep,
                    "days": baseline_case.restart_timesteps[timestep]["days"],
                    "equal": bool(np.array_equal(left, right)),
                    "max_abs_difference": float(np.nanmax(np.abs(left - right))),
                }
            )
        dynamic[keyword] = differences

    return {
        "case_name": case_root.name,
        "changed_scenario_fields": changed_fields,
        "static": static,
        "dynamic": dynamic,
        "static_invariants_hold": all(item["equal"] for item in static.values()),
        "dynamic_outputs_differ": any(not item["equal"] for values in dynamic.values() for item in values),
    }


def compare_outputs(output_root: Path, baseline_name: str | None = None) -> dict[str, object]:
    case_roots = sorted(path for path in output_root.iterdir() if path.is_dir())
    if not case_roots:
        return {"valid": False, "error": "no scenario directories found"}
    if baseline_name is None:
        baseline_root = case_roots[0]
    else:
        baseline_root = output_root / baseline_name
        if baseline_root not in case_roots:
            return {"valid": False, "error": f"baseline scenario not found: {baseline_name}"}
    comparisons = [compare_case(baseline_root, case_root) for case_root in case_roots if case_root != baseline_root]
    return {
        "output_root": str(output_root),
        "baseline": baseline_root.name,
        "cases": [case_root.name for case_root in case_roots],
        "comparisons": comparisons,
        "valid": bool(comparisons) and all(item["static_invariants_hold"] and item["dynamic_outputs_differ"] for item in comparisons),
    }


def main() -> int:
    args = parse_args()
    report = compare_outputs(args.output_root, args.baseline)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for comparison in report.get("comparisons", []):
        status = "OK" if comparison["static_invariants_hold"] and comparison["dynamic_outputs_differ"] else "FAILED"
        print(f"{status}: {comparison['case_name']} vs {report['baseline']}")
        print(f"  changed scenario fields: {', '.join(comparison['changed_scenario_fields']) or 'none'}")
    if not report.get("comparisons"):
        print(f"FAILED: {report.get('error', 'no comparisons made')}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
