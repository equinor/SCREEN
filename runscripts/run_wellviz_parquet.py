#!/usr/bin/env python3
"""Build and serve one scenario's Parquet-backed WellViz package."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--all-records", action="store_true")
    parser.add_argument("--timing", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def load_server_module():
    script = Path(__file__).with_name("serve_wellviz_parquet.py")
    spec = importlib.util.spec_from_file_location("serve_wellviz_parquet", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load server script: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or args.results_root / f"{args.case}_wellviz_indexed"
    export_command = [
        sys.executable,
        str(Path(__file__).with_name("export_wellviz_indexed.py")),
        "--results-root",
        str(args.results_root),
        "--case",
        args.case,
        "--output-dir",
        str(output_dir),
    ]
    if args.all_records:
        export_command.append("--all-records")
    if args.timing:
        export_command.append("--timing")

    subprocess.run(export_command, cwd=Path(__file__).parents[1], check=True)
    server = load_server_module()
    print(f"Serving WellViz package at http://{args.host}:{args.port}")
    server.create_app(output_dir).run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
