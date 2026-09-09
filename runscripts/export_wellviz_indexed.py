#!/usr/bin/env python3
"""Export an indexed, server-served WellViz XZ data package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from export_wellviz_xz import _matrix, _numeric_keywords

from src.GaP.libs.visualization import ResdataCase

INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>SCREEN WellViz XZ</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{font-family:sans-serif;margin:1rem}#controls{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}label{display:flex;flex-direction:column}#plot{width:100%}</style></head>
<body><h1>SCREEN WellViz XZ</h1><div id="controls">
<label>Source<select id="source"></select></label><label>Property<select id="property"></select></label>
<label>J column<select id="j-column"></select></label><label>Z scale<input id="z-scale" type="number" min="0.00001" step="0.0001" value="0.001"></label></div>
<div id="status">Loading manifest...</div><div id="plot"></div><script>
const source=document.getElementById('source'), property=document.getElementById('property'), jColumn=document.getElementById('j-column'), zScale=document.getElementById('z-scale'), status=document.getElementById('status');
let manifest;
async function loadManifest(){ manifest=await fetch('manifest.json').then(r=>r.json()); for(const name of manifest.sources) source.add(new Option(name,name)); for(const j of manifest.j_columns) jColumn.add(new Option(`J ${j}`,j)); source.value=manifest.sources[0]; jColumn.value=manifest.middle_j; updateProperties(); }
function updateProperties(){ property.replaceChildren(...manifest.properties[source.value].map(name=>new Option(name,name))); property.value=manifest.properties[source.value][0]; render(); }
async function render(){ if(!manifest||!property.value)return; const key=`/api/data?source=${source.value}&property=${property.value}&j=${jColumn.value}`; status.textContent=`Loading ${key}...`; const item=await fetch(key).then(r=>r.json()); const scale=Number(zScale.value)||0.001; Plotly.react('plot',[{x:item.x,y:item.z.map(v=>v*scale),z:item.values,customdata:item.hover,type:'heatmap',colorscale:'Viridis',colorbar:{title:property.value},connectgaps:false,zsmooth:false,hovertemplate:`${property.value}: %{customdata[0]:.6g}<br>ijk: %{customdata[1]:.0f} %{customdata[2]:.0f} %{customdata[3]:.0f}<extra></extra>`}],{title:`${source.value} | ${property.value} | J=${jColumn.value}`,xaxis:{title:'X [m]'},yaxis:{title:`Z scaled by ${scale} [m]`,autorange:'reversed'},height:900,template:'plotly_white'}); status.textContent='Ready'; }
source.addEventListener('change',()=>{updateProperties()}); property.addEventListener('change',render); jColumn.addEventListener('change',render); zScale.addEventListener('input',render); loadManifest().catch(error=>{status.textContent=error});
</script></body></html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def write_package(case: ResdataCase, case_name: str, output_dir: Path) -> None:
    lgr = case.embedded_lgr()
    if lgr is None:
        raise ValueError("The selected case has no embedded LGR")
    sources = {source: _numeric_keywords(case, source) for source in ("INIT", "UNRST")}
    j_columns = list(range(lgr.get_dims()[1]))
    rows = []
    for source, keywords in sources.items():
        for keyword in keywords:
            for j_column in j_columns:
                x_values, z_values, matrix, hover = _matrix(case, source, keyword, j_column, 0, 1.0)
                for row_index, z_value in enumerate(z_values):
                    for column_index, x_value in enumerate(x_values):
                        value = matrix[row_index, column_index]
                        if not pd.isna(value):
                            rows.append(
                                {
                                    "source": source,
                                    "property": keyword,
                                    "j_column": j_column,
                                    "x": x_value,
                                    "z": z_value,
                                    "value": value,
                                    "i": hover[row_index, column_index, 1],
                                    "j": hover[row_index, column_index, 2],
                                    "k": hover[row_index, column_index, 3],
                                }
                            )
    manifest = {
        "case": case_name,
        "sources": list(sources),
        "properties": sources,
        "j_columns": j_columns,
        "middle_j": lgr.get_dims()[1] // 2,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(output_dir / "data.parquet", index=False)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")


def main() -> int:
    args = parse_args()
    case = ResdataCase(args.results_root / args.case / "model" / "TEMP-0")
    write_package(case, args.case, args.output_dir)
    print(f"Wrote indexed WellViz package: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
