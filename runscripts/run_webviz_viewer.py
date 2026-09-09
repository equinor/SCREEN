#!/usr/bin/env python3
"""Serve a predefined Webviz view for SCREEN simulator results."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase, hexahedron_polygons


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True, help="Directory containing one subdirectory per scenario.")
    parser.add_argument("--case", dest="case_name", help="Initial scenario name; defaults to the first available case.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def _case_prefix(results_root: Path, case_name: str) -> Path:
    return results_root / case_name / "model" / "TEMP-0"


def _case_names(results_root: Path) -> list[str]:
    return sorted(path.name for path in results_root.iterdir() if path.is_dir() and (path / "model" / "TEMP-0.EGRID").exists())


def _payload(case: ResdataCase, source: str, keyword: str) -> dict[str, list[float] | list[int]]:
    data = case.lgr_property_slice(source, keyword)
    properties = np.repeat(data["properties"], 6)
    return {
        "points": data["corners"].reshape(-1, 3).astype(np.float32).ravel().tolist(),
        "polys": hexahedron_polygons(len(data["corners"])),
        "properties": properties.astype(np.float32).tolist(),
    }


def create_app(results_root: Path):
    try:
        import dash
        import webviz_subsurface_components as wsc
        from dash import Input, Output, dcc, html
    except ImportError as exc:
        raise RuntimeError(
            "The Webviz viewer requires optional dependencies. Install with " "`uv pip install webviz-subsurface-components`."
        ) from exc

    cases = _case_names(results_root)
    if not cases:
        raise ValueError(f"No result cases found under {results_root}")
    loaded_cases = {name: ResdataCase(_case_prefix(results_root, name)) for name in cases}

    app = dash.Dash(__name__)
    app.layout = html.Div(
        [
            html.H2("SCREEN Webviz viewer"),
            html.Div(
                [
                    dcc.Dropdown(cases, cases[0], id="case", clearable=False),
                    dcc.Dropdown(["INIT", "UNRST"], "INIT", id="source", clearable=False),
                    dcc.Dropdown(id="keyword", clearable=False),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 2fr", "gap": "8px"},
            ),
            html.Div(id="viewer", style={"height": "80vh", "width": "100%"}),
        ],
        style={"fontFamily": "sans-serif", "padding": "16px"},
    )

    @app.callback(Output("keyword", "options"), Output("keyword", "value"), Input("case", "value"), Input("source", "value"))
    def update_keywords(case_name: str, source: str):
        keywords = loaded_cases[case_name].keywords if source == "INIT" else loaded_cases[case_name].restart_keywords
        numeric = [
            keyword
            for keyword in keywords
            if keyword not in {"SEQNUM", "INTEHEAD", "LOGIHEAD", "DOUBHEAD", "LGR", "LGRNAMES", "LGRHEADI", "LGRHEADQ", "LGRHEADD", "LGRSGONE"}
        ]
        return [{"label": keyword, "value": keyword} for keyword in numeric], numeric[0] if numeric else None

    @app.callback(Output("viewer", "children"), Input("case", "value"), Input("source", "value"), Input("keyword", "value"))
    def update_viewer(case_name: str, source: str, keyword: str):
        if not keyword:
            return html.Div("No numeric properties available")
        layer_url = f"/screen-data/{case_name}/{source}/{keyword}"
        return wsc.SubsurfaceViewer(
            id="screen-viewer",
            layers=[
                {
                    "@@type": "Grid3DLayer",
                    "id": "screen-lgr-middle-j",
                    "pointsData": f"{layer_url}/points",
                    "polysData": f"{layer_url}/polys",
                    "propertiesData": f"{layer_url}/properties",
                    "colorMapName": "Rainbow",
                    "coloringMode": "Property",
                    "gridLines": True,
                    "material": False,
                    "ZIncreasingDownwards": False,
                }
            ],
            views={
                "layout": [1, 1],
                "showLabel": True,
                "viewports": [{"id": "screen-xz", "show3D": True, "name": "South XZ", "layerIds": ["screen-lgr-middle-j"]}],
            },
            verticalScale=0.005,
            coordinateUnit="m",
        )

    @app.server.route("/screen-data/<case_name>/<source>/<keyword>/<kind>")
    def screen_data(case_name: str, source: str, keyword: str, kind: str):
        from flask import jsonify

        payload = _payload(loaded_cases[case_name], source, keyword)
        return jsonify(payload[kind])

    return app


def main() -> int:
    args = parse_args()
    app = create_app(args.results_root)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
