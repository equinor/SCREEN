#!/usr/bin/env python3
"""Export a historical WellViz-style interactive Plotly XZ heatmap."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", choices=("INIT", "UNRST"), default="INIT")
    parser.add_argument("--property", dest="keyword", default="PORV")
    parser.add_argument("--j-column", type=int, default=None)
    parser.add_argument("--record", type=int, default=0, help="UNRST record/timestep index.")
    parser.add_argument("--z-scale", type=float, default=0.001)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _case_prefix(results_root: Path, case_name: str) -> Path:
    return results_root / case_name / "model" / "TEMP-0"


def _matrix(case: ResdataCase, source: str, keyword: str, j_column: int | None, record: int, z_scale: float):
    data = case.lgr_property_slice(source, keyword, record=record, j=j_column)
    if not len(data["centers"]):
        raise ValueError("The selected case has no embedded LGR cells")
    centers = data["centers"]
    x_values = np.unique(np.round(centers[:, 0], 8))
    z_values = np.unique(np.round(centers[:, 2], 8))
    x_index = {value: index for index, value in enumerate(x_values)}
    z_index = {value: index for index, value in enumerate(z_values)}
    matrix = np.full((len(z_values), len(x_values)), np.nan)
    hover = np.full((len(z_values), len(x_values), 4), np.nan)
    lgr_index = case.embedded_lgr().export_index()
    for center, value, cell_index in zip(centers, data["properties"], data["indices"]):
        ix = x_index[round(center[0], 8)]
        iz = z_index[round(center[2], 8)]
        matrix[iz, ix] = value
        row = lgr_index.iloc[int(cell_index)]
        hover[iz, ix] = [value, row["i"], row["j"], row["k"]]
    return x_values, z_values * z_scale, matrix, hover


def build_figure(case: ResdataCase, source: str, keyword: str, j_column: int | None, record: int, z_scale: float):
    import plotly.graph_objects as go

    x_values, z_values, matrix, hover = _matrix(case, source, keyword, j_column, record, z_scale)
    heatmap = go.Heatmap(
        x=x_values,
        y=z_values,
        z=matrix,
        customdata=hover,
        colorscale="Viridis",
        colorbar={"title": keyword},
        hovertemplate=f"{keyword}: %{{customdata[0]:.6g}}<br>ijk: %{{customdata[1]:.0f}} %{{customdata[2]:.0f}} %{{customdata[3]:.0f}}<extra></extra>",
        connectgaps=False,
        zsmooth=False,
    )
    figure = go.Figure(heatmap)
    figure.update_layout(
        title=f"{case.prefix.parent.parent.name} | {source} | {keyword} | J={j_column if j_column is not None else 'middle'}",
        xaxis_title="X [m]",
        yaxis_title=f"Z scaled by {z_scale:g} [m]",
        yaxis={"autorange": "reversed"},
        height=900,
        template="plotly_white",
    )
    return figure


def main() -> int:
    args = parse_args()
    if args.z_scale <= 0:
        raise ValueError("--z-scale must be positive")
    case = ResdataCase(_case_prefix(args.results_root, args.case))
    figure = build_figure(case, args.source, args.keyword, args.j_column, args.record, args.z_scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(args.output, include_plotlyjs=True, full_html=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
