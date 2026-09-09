#!/usr/bin/env python3
"""Export one SCREEN simulator result as a standalone XZ HTML viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", choices=("INIT", "UNRST"), default="INIT")
    parser.add_argument("--property", dest="keyword", default="PORV")
    parser.add_argument("--j-column", type=int, default=None, help="LGR J column; defaults to the middle column.")
    parser.add_argument("--z-scale", type=float, default=0.001)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _case_prefix(results_root: Path, case_name: str) -> Path:
    return results_root / case_name / "model" / "TEMP-0"


def _colour(value: float, minimum: float, maximum: float) -> str:
    if not np.isfinite(value):
        return "#bdbdbd"
    fraction = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
    fraction = min(max(fraction, 0.0), 1.0)
    red = int(255 * fraction)
    blue = int(255 * (1.0 - fraction))
    return f"rgb({red},80,{blue})"


def _polygon(corners: np.ndarray, z_scale: float) -> str:
    points = np.column_stack((corners[:, 0], corners[:, 2] * z_scale))
    center = points.mean(axis=0)
    order = np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))
    return " ".join(f"{points[index, 0]:.6g},{points[index, 1]:.6g}" for index in order)


def render(case: ResdataCase, source: str, keyword: str, j_column: int | None, z_scale: float) -> str:
    data = case.lgr_property_slice(source, keyword, j=j_column)
    if not len(data["corners"]):
        raise ValueError("The selected result has no embedded LGR geometry")
    properties = data["properties"]
    minimum = float(np.nanmin(properties))
    maximum = float(np.nanmax(properties))
    polygons = []
    for corners, value in zip(data["corners"], properties):
        polygons.append(f'<polygon points="{_polygon(corners, z_scale)}" fill="{_colour(value, minimum, maximum)}" ' f'data-value="{value:.8g}" />')
    payload = {
        "case": case.prefix.parent.parent.name,
        "source": source,
        "property": keyword,
        "j_column": case.embedded_lgr().get_dims()[1] // 2 if j_column is None else j_column,
        "z_scale": z_scale,
        "minimum": minimum,
        "maximum": maximum,
    }
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SCREEN XZ view</title>
<style>body{{font-family:sans-serif;margin:1rem}} svg{{border:1px solid #ccc;width:100%;height:80vh;background:#fff}} polygon{{stroke:#111;stroke-width:.15}} #info{{margin:.5rem 0}}</style></head>
<body><h1>SCREEN XZ viewer</h1><div id="info"></div>
<svg id="view" viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet"></svg>
<script>
const metadata={json.dumps(payload)};
const svg=document.getElementById('view');
const polygons=[...svg.querySelectorAll('polygon')];
document.getElementById('info').textContent=`${{metadata.case}} | ${{metadata.source}} | ${{metadata.property}} | J ${{metadata.j_column}} | Z scale ${{metadata.z_scale}}`;
svg.innerHTML={json.dumps(''.join(polygons))};
const shapes=[...svg.querySelectorAll('polygon')];
const all=shapes.flatMap(p=>p.getAttribute('points').split(' ').map(x=>x.split(',').map(Number)));
const xs=all.map(p=>p[0]), ys=all.map(p=>p[1]); const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
svg.setAttribute('viewBox',`${{xmin}} ${{ymin}} ${{xmax-xmin}} ${{ymax-ymin}}`);
</script></body></html>"""


def main() -> int:
    args = parse_args()
    if args.z_scale <= 0:
        raise ValueError("--z-scale must be positive")
    case = ResdataCase(_case_prefix(args.results_root, args.case))
    output = render(case, args.source, args.keyword, args.j_column, args.z_scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
