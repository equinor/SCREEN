#!/usr/bin/env python3
"""Compare static and dynamic outputs from a scenario batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase

LGR_FILE = Path("include/TEMP_LGR.grdecl")
DYNAMIC_KEYWORDS = ("PRESSURE", "SWAT", "SGAS")
INIT_PROPERTIES = ("PERMX", "PERMY", "PERMZ", "PORO", "PORV", "EQLNUM", "SATNUM")
LGR_PROPERTY_KEYWORDS = {"PERMX", "PERMY", "PERMZ", "PORO", "PORV", "EQLNUM", "SATNUM", "FIPLEG", "FIPNUM", "MULTX", "MULTY", "MULTZ"}
GEOMETRY_POLICY_FIELDS = {
    "top_depth",
    "water_depth",
    "reservoir_thickness",
    "target_dz_water",
    "target_dz_overburden",
    "target_dz_reservoir",
    "min_water_layers",
    "min_overburden_layers",
    "min_reservoir_layers",
    "max_water_layers",
    "max_overburden_layers",
    "max_reservoir_layers",
    "cells_per_layer",
    "nx",
    "ny",
    "dx",
    "dy",
    "aquifer_layers",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--baseline", help="Baseline scenario directory name; defaults to the first sorted case.")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def scenario_payload(case_root: Path) -> dict[str, object]:
    path = case_root / "scenario.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def grid_policy_payload(case_root: Path) -> dict[str, object]:
    path = case_root / "grid_policy.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lgr_geometry_signature(path: Path) -> tuple[str, ...] | None:
    """Normalize LGR instructions, ignoring assigned property values."""
    if not path.is_file():
        return None
    normalized_lines = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        statement = line.split("--", 1)[0].strip()
        if not statement:
            continue
        tokens = statement.split()
        if tokens[0].upper() in LGR_PROPERTY_KEYWORDS and len(tokens) > 2:
            tokens[1] = "<property-value>"
        normalized_lines.append(" ".join(tokens))
    return tuple(normalized_lines)


def compare_init_properties(baseline_case: ResdataCase, case_data: ResdataCase) -> dict[str, object]:
    comparisons: dict[str, object] = {}
    for keyword in INIT_PROPERTIES:
        if keyword not in baseline_case.keywords or keyword not in case_data.keywords:
            comparisons[keyword] = {"available": False, "equal": None}
            continue
        baseline_values = baseline_case.init_vector(keyword)
        case_values = case_data.init_vector(keyword)
        if baseline_values.shape != case_values.shape:
            comparisons[keyword] = {
                "available": True,
                "compatible": False,
                "equal": False,
                "baseline_shape": list(baseline_values.shape),
                "case_shape": list(case_values.shape),
            }
            continue
        differences = np.abs(baseline_values - case_values)
        finite_differences = differences[np.isfinite(differences)]
        comparisons[keyword] = {
            "available": True,
            "compatible": True,
            "equal": bool(np.array_equal(baseline_values, case_values, equal_nan=True)),
            "changed_cells": int(np.count_nonzero(~np.isclose(baseline_values, case_values, rtol=1e-7, atol=0, equal_nan=True))),
            "max_abs_difference": float(finite_differences.max()) if finite_differences.size else 0.0,
        }
    return comparisons


def compare_case(baseline_root: Path, case_root: Path) -> dict[str, object]:
    baseline = scenario_payload(baseline_root)
    case = scenario_payload(case_root)
    changed_scenario_fields = sorted(key for key in set(baseline) | set(case) if key != "case_name" and baseline.get(key) != case.get(key))
    baseline_policy_path = baseline_root / "grid_policy.json"
    case_policy_path = case_root / "grid_policy.json"
    baseline_policy = grid_policy_payload(baseline_root)
    case_policy = grid_policy_payload(case_root)
    grid_policy_comparison_available = baseline_policy_path.is_file() and case_policy_path.is_file()
    changed_grid_policy_fields = (
        sorted(key for key in set(baseline_policy) | set(case_policy) if baseline_policy.get(key) != case_policy.get(key))
        if grid_policy_comparison_available
        else []
    )
    geometry_policy_fields_changed = sorted(set(changed_grid_policy_fields) & GEOMETRY_POLICY_FIELDS)

    dynamic: dict[str, object] = {}
    baseline_case = ResdataCase(baseline_root / "model" / "TEMP-0")
    case_data = ResdataCase(case_root / "model" / "TEMP-0")
    baseline_corners = baseline_case.cell_corners()
    case_corners = case_data.cell_corners()
    dimensions_equal = baseline_case.dimensions == case_data.dimensions
    cell_corners_equal = baseline_corners.shape == case_corners.shape and bool(
        np.allclose(baseline_corners, case_corners, rtol=0, atol=1e-6, equal_nan=True)
    )
    baseline_lgr_geometry = lgr_geometry_signature(baseline_root / LGR_FILE)
    case_lgr_geometry = lgr_geometry_signature(case_root / LGR_FILE)
    lgr_geometry_equal = baseline_lgr_geometry is not None and baseline_lgr_geometry == case_lgr_geometry
    geometry_invariants_hold = dimensions_equal and cell_corners_equal and lgr_geometry_equal

    init_properties = compare_init_properties(baseline_case, case_data)
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
                    "max_abs_difference": float(np.nanmax(np.abs(left - right))) if left.shape == right.shape else None,
                    "compatible": left.shape == right.shape,
                }
            )
        dynamic[keyword] = differences

    dynamic_outputs_differ = any(item["compatible"] and not item["equal"] for values in dynamic.values() for item in values)
    validation_errors = []
    if not geometry_invariants_hold:
        validation_errors.append("grid geometry changed in initialization/physics sensitivity mode")
    if geometry_policy_fields_changed:
        validation_errors.append("geometry-affecting GridPolicy fields changed; compare these cases as a grid sensitivity study")
    if not dynamic_outputs_differ:
        validation_errors.append("selected dynamic outputs did not differ")

    return {
        "case_name": case_root.name,
        "changed_scenario_fields": changed_scenario_fields,
        "changed_grid_policy_fields": changed_grid_policy_fields,
        "grid_policy_comparison_available": grid_policy_comparison_available,
        "geometry_policy_fields_changed": geometry_policy_fields_changed,
        "grid_geometry": {
            "dimensions_equal": dimensions_equal,
            "cell_corners_equal": cell_corners_equal,
            "lgr_geometry_equal": lgr_geometry_equal,
        },
        "init_properties": init_properties,
        "dynamic": dynamic,
        "geometry_invariants_hold": geometry_invariants_hold,
        "dynamic_outputs_differ": dynamic_outputs_differ,
        "valid": not validation_errors,
        "validation_errors": validation_errors,
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
        "mode": "initialization_physics_sensitivity",
        "output_root": str(output_root),
        "baseline": baseline_root.name,
        "cases": [case_root.name for case_root in case_roots],
        "comparisons": comparisons,
        "valid": bool(comparisons) and all(item["valid"] for item in comparisons),
    }


def main() -> int:
    args = parse_args()
    report = compare_outputs(args.output_root, args.baseline)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for comparison in report.get("comparisons", []):
        status = "OK" if comparison["valid"] else "FAILED"
        print(f"{status}: {comparison['case_name']} vs {report['baseline']}")
        print(f"  changed scenario fields: {', '.join(comparison['changed_scenario_fields']) or 'none'}")
        print(f"  changed GridPolicy fields: {', '.join(comparison['changed_grid_policy_fields']) or 'none'}")
        print(f"  GridPolicy metadata available: {comparison['grid_policy_comparison_available']}")
        print(
            f"  changed INIT properties: {', '.join(key for key, value in comparison['init_properties'].items() if value.get('equal') is False) or 'none'}"
        )
        for error in comparison["validation_errors"]:
            print(f"  {error}")
    if not report.get("comparisons"):
        print(f"FAILED: {report.get('error', 'no comparisons made')}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
