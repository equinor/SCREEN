#!/usr/bin/env python3
"""Validate files produced by the multi-scenario workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REQUIRED_FILES = (
    Path("include/TEMP_GRD.grdecl"),
    Path("include/TEMP_LGR.grdecl"),
    Path("model/TEMP-0.EGRID"),
    Path("model/TEMP-0.INIT"),
)
ERROR_PATTERN = re.compile(r"\b(error|fatal|failed)\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True, help="Batch output directory containing case subdirectories.")
    parser.add_argument("--report", type=Path, help="Write the validation report as JSON.")
    return parser.parse_args()


def file_info(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"size": path.stat().st_size, "sha256": digest.hexdigest()}


def validate_case(case_root: Path) -> dict[str, object]:
    missing = []
    files: dict[str, dict[str, int | str]] = {}
    for relative_path in REQUIRED_FILES:
        path = case_root / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(str(relative_path))
        else:
            files[str(relative_path)] = file_info(path)

    log_errors = []
    log_root = case_root / "logs"
    for log_path in sorted(log_root.glob("*.log")):
        for line_number, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if ERROR_PATTERN.search(line):
                log_errors.append(f"{log_path.name}:{line_number}: {line.strip()}")

    errors = [f"missing or empty file: {path}" for path in missing]
    errors.extend(f"log error: {message}" for message in log_errors)
    return {
        "case_name": case_root.name,
        "valid": not errors,
        "files": files,
        "errors": errors,
    }


def validate_outputs(output_root: Path) -> dict[str, object]:
    case_roots = sorted(path for path in output_root.iterdir() if path.is_dir()) if output_root.is_dir() else []
    cases = [validate_case(case_root) for case_root in case_roots]
    return {
        "output_root": str(output_root),
        "valid": bool(cases) and all(case["valid"] for case in cases),
        "cases": cases,
    }


def main() -> int:
    args = parse_args()
    report = validate_outputs(args.output_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for case in report["cases"]:
        status = "OK" if case["valid"] else "FAILED"
        print(f"{status}: {case['case_name']}")
        for error in case["errors"]:
            print(f"  {error}")
    if not report["cases"]:
        print(f"FAILED: no scenario directories found under {args.output_root}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
