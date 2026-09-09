#!/usr/bin/env python3
"""Export a historical WellViz-style interactive Plotly XZ heatmap."""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
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
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser.")
    parser.add_argument("--timing", action="store_true", help="Print phase timing information.")
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
    lgr_i = lgr_index["i"].to_numpy()
    lgr_j = lgr_index["j"].to_numpy()
    lgr_k = lgr_index["k"].to_numpy()
    for center, value, cell_index in zip(centers, data["properties"], data["indices"]):
        ix = x_index[round(center[0], 8)]
        iz = z_index[round(center[2], 8)]
        matrix[iz, ix] = value
        index = int(cell_index)
        hover[iz, ix] = [value, lgr_i[index], lgr_j[index], lgr_k[index]]
    return x_values, z_values * z_scale, matrix, hover


def _numeric_keywords(case: ResdataCase, source: str) -> list[str]:
    keywords = case.keywords if source == "INIT" else case.restart_keywords
    excluded = {"SEQNUM", "INTEHEAD", "LOGIHEAD", "DOUBHEAD", "LGR", "LGRNAMES", "LGRHEADI", "LGRHEADQ", "LGRHEADD", "LGRSGONE"}
    result = []
    for keyword in keywords:
        if keyword in excluded:
            continue
        try:
            values = case.init_vector(keyword) if source == "INIT" else case.restart[keyword][0].numpy_view()
            if np.issubdtype(np.asarray(values).dtype, np.number):
                result.append(keyword)
        except (KeyError, ValueError, TypeError):
            continue
    return result


def _json_array(values: np.ndarray) -> list:
    return [None if not np.isfinite(value) else float(value) for value in np.asarray(values).ravel()]


def _json_matrix(values: np.ndarray) -> list[list[float | None]]:
    return [[None if not np.isfinite(value) else float(value) for value in row] for row in np.asarray(values)]


def _json_cube(values: np.ndarray) -> list[list[list[float | None]]]:
    return [[[None if not np.isfinite(value) else float(value) for value in cell] for cell in row] for row in np.asarray(values)]


def _interactive_html(
    case: ResdataCase,
    sources: dict[str, list[str]],
    j_columns: list[int],
    record: int,
    z_scale: float,
    initial_source: str,
    initial_keyword: str,
    initial_j: int,
    timing: dict[str, float] | None = None,
) -> str:
    data = {}
    matrix_started = time.perf_counter()
    for source, keywords in sources.items():
        for keyword in keywords:
            for j_column in j_columns:
                x_values, z_values, matrix, hover = _matrix(case, source, keyword, j_column, record, 1.0)
                data[f"{source}|{keyword}|{j_column}"] = {
                    "x": _json_array(x_values),
                    "z": _json_array(z_values),
                    "values": _json_matrix(matrix),
                    "hover": _json_cube(hover),
                }
    if timing is not None:
        timing["matrix_and_serialization"] = time.perf_counter() - matrix_started
    figure = build_figure(case, initial_source, initial_keyword, initial_j, record, z_scale)
    plot_html = figure.to_html(full_html=False, include_plotlyjs=True, div_id="wellviz-xz-plot")
    metadata = json.dumps(
        {
            "data": data,
            "sources": sources,
            "j_columns": j_columns,
            "z_scale": z_scale,
            "initial_source": initial_source,
            "initial_keyword": initial_keyword,
            "initial_j": initial_j,
        }
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>WellViz XZ</title>
<style>body{{font-family:sans-serif;margin:1rem}} #controls{{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}} label{{display:flex;flex-direction:column}} #wellviz-xz-plot{{width:100%}}</style></head>
<body><h1>WellViz XZ viewer</h1><div id="controls">
<label>Source<select id="source"></select></label><label>Property<select id="property"></select></label>
<label>J column<select id="j-column"></select></label><label>Z scale<input id="z-scale" type="number" min="0.00001" step="0.0001"></label></div>
{plot_html}
<script>
const model={metadata}; const source=document.getElementById('source'), property=document.getElementById('property'), jColumn=document.getElementById('j-column'), zScale=document.getElementById('z-scale');
for (const name of Object.keys(model.sources)) source.add(new Option(name,name)); source.value=model.initial_source; zScale.value=model.z_scale;
for (const j of model.j_columns) jColumn.add(new Option(`J ${{j}}`,j)); jColumn.value=model.initial_j;
function properties() {{ property.replaceChildren(...model.sources[source.value].map(name => new Option(name,name))); property.value=model.initial_keyword; }}
function render() {{ const item=model.data[`${{source.value}}|${{property.value}}|${{jColumn.value}}`]; if (!item) return; const scale=Number(zScale.value)||model.z_scale; const custom=item.hover.map(row => row.map(cell => cell === null ? null : cell)); Plotly.react('wellviz-xz-plot',[{{x:item.x,y:item.z.map(value => value*scale),z:item.values,customdata:custom,type:'heatmap',colorscale:'Viridis',colorbar:{{title:property.value}},connectgaps:false,zsmooth:false,hovertemplate:`${{property.value}}: %{{customdata[0]:.6g}}<br>ijk: %{{customdata[1]:.0f}} %{{customdata[2]:.0f}} %{{customdata[3]:.0f}}<extra></extra>`}}],{{title:`${{source.value}} | ${{property.value}} | J=${{jColumn.value}}`,xaxis:{{title:'X [m]'}},yaxis:{{title:`Z scaled by ${{scale}} [m]`,autorange:'reversed'}},height:900,template:'plotly_white'}}); }}
source.addEventListener('change',() => {{ properties(); render(); }}); property.addEventListener('change',render); jColumn.addEventListener('change',render); zScale.addEventListener('input',render); properties(); render();
</script></body></html>"""


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
    timing: dict[str, float] = {}
    started = time.perf_counter()
    case = ResdataCase(_case_prefix(args.results_root, args.case))
    timing["case_load"] = time.perf_counter() - started
    sources = {source: _numeric_keywords(case, source) for source in ("INIT", "UNRST")}
    for source in sources:
        if not sources[source]:
            raise ValueError(f"No numeric {source} properties available")
    initial_keyword = args.keyword if args.keyword in sources[args.source] else sources[args.source][0]
    j_columns = list(range(case.embedded_lgr().get_dims()[1]))
    initial_j = case.embedded_lgr().get_dims()[1] // 2 if args.j_column is None else args.j_column
    output = _interactive_html(case, sources, j_columns, args.record, args.z_scale, args.source, initial_keyword, initial_j, timing)
    timing["total_before_write"] = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_started = time.perf_counter()
    args.output.write_text(output, encoding="utf-8")
    timing["html_write"] = time.perf_counter() - write_started
    print(f"Wrote WellViz XZ HTML: {args.output} ({args.output.stat().st_size / 1024**2:.1f} MB)")
    if args.timing:
        print("Timing:")
        for name, elapsed in timing.items():
            print(f"  {name}: {elapsed:.3f}s")
    if args.open:
        webbrowser.open(args.output.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
