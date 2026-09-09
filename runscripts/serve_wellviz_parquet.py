#!/usr/bin/env python3
"""Serve an indexed WellViz Parquet package with filtered JSON responses."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory


def create_app(package_dir: Path) -> Flask:
    app = Flask(__name__, static_folder=str(package_dir), static_url_path="")
    data = pd.read_parquet(package_dir / "data.parquet")

    @app.get("/api/data")
    def data_endpoint():
        j_column = int(request.args["j"])
        selected = data[(data["source"] == request.args["source"]) & (data["property"] == request.args["property"]) & (data["j_column"] == j_column)]
        if selected.empty:
            return jsonify({"x": [], "z": [], "values": [], "hover": []}), 404
        x_values = sorted(selected["x"].unique())
        z_values = sorted(selected["z"].unique())
        x_index = {value: index for index, value in enumerate(x_values)}
        z_index = {value: index for index, value in enumerate(z_values)}
        values = [[None for _ in x_values] for _ in z_values]
        hover = [[[None, None, None, None] for _ in x_values] for _ in z_values]
        for row in selected.itertuples():
            iz = z_index[row.z]
            ix = x_index[row.x]
            values[iz][ix] = row.value
            hover[iz][ix] = [row.value, row.i, row.j, row.k]
        return jsonify({"x": x_values, "z": z_values, "values": values, "hover": hover})

    @app.get("/")
    def index():
        return send_from_directory(package_dir, "index.html")

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_app(args.package_dir).run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
