#!/usr/bin/env python3
"""Export an indexed, server-served WellViz XZ data package."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from export_wellviz_xz import _matrix, _numeric_keywords

from src.GaP.libs.visualization import ResdataCase

INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>SCREEN WellViz XZ</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{font-family:sans-serif;margin:1rem}#controls{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}label{display:flex;flex-direction:column}#plot{width:100%}</style></head>
<body><h1>SCREEN WellViz XZ</h1><div id="controls">
<label>Source<select id="source"></select></label><label>Property<select id="property"></select></label><label>Timestep<select id="record"></select></label>
<label>J column<select id="j-column"></select></label><label>X min<input id="x-min" type="number"></label><label>X max<input id="x-max" type="number"></label><label>Y min<input id="y-min" type="number"></label><label>Y max<input id="y-max" type="number"></label></div>
<div id="status">Loading manifest...</div><div id="plot"></div><script>
const source=document.getElementById('source'), property=document.getElementById('property'), record=document.getElementById('record'), jColumn=document.getElementById('j-column'), xmin=document.getElementById('x-min'), xmax=document.getElementById('x-max'), ymin=document.getElementById('y-min'), ymax=document.getElementById('y-max'), status=document.getElementById('status');
let manifest;
async function loadManifest(){ manifest=await fetch('manifest.json').then(r=>r.json()); for(const name of manifest.sources) source.add(new Option(name,name)); for(const step of manifest.timesteps) record.add(new Option(`step ${step.record} (${step.days} days)`,step.record)); for(const j of manifest.j_columns) jColumn.add(new Option(`J ${j}`,j)); source.value=manifest.sources[0]; record.value=0; jColumn.value=manifest.middle_j; xmin.value=manifest.bounds.x_min; xmax.value=manifest.bounds.x_max; ymin.value=manifest.bounds.y_min; ymax.value=manifest.bounds.y_max; updateProperties(); }
function updateProperties(){ property.replaceChildren(...manifest.properties[source.value].map(name=>new Option(name,name))); property.value=manifest.properties[source.value][0]; render(); }
async function render(){ if(!manifest||!property.value)return; const key=`/api/data?source=${source.value}&property=${property.value}&record=${record.value}&j=${jColumn.value}`; status.textContent=`Loading ${key}...`; const item=await fetch(key).then(r=>r.json()); Plotly.react('plot',[{x:item.x,y:item.z,z:item.values,customdata:item.hover,type:'heatmap',colorscale:'Viridis',colorbar:{title:property.value},connectgaps:false,zsmooth:false,hovertemplate:`${property.value}: %{customdata[0]:.6g}<br>ijk: %{customdata[1]:.0f} %{customdata[2]:.0f} %{customdata[3]:.0f}<extra></extra>`}],{title:`${source.value} | ${property.value} | step=${record.value} | J=${jColumn.value}`,xaxis:{title:'X [m]',range:[Number(xmin.value),Number(xmax.value)]},yaxis:{title:'Depth [m]',range:[Number(ymin.value),Number(ymax.value)],autorange:false},height:900,template:'plotly_white'}); status.textContent='Ready'; }
source.addEventListener('change',()=>{updateProperties()}); property.addEventListener('change',render); record.addEventListener('change',render); jColumn.addEventListener('change',render); [xmin,xmax,ymin,ymax].forEach(control=>control.addEventListener('change',render)); loadManifest().catch(error=>{status.textContent=error});
</script></body></html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timing", action="store_true", help="Print phase timing information.")
    parser.add_argument("--all-records", action="store_true", help="Include every logical UNRST timestep instead of timestep 0 only.")
    return parser.parse_args()


def write_package(
    case: ResdataCase,
    case_name: str,
    output_dir: Path,
    timing: dict[str, float] | None = None,
    sources: dict[str, list[str]] | None = None,
    records: dict[str, list[int]] | None = None,
) -> None:
    lgr = case.embedded_lgr()
    if lgr is None:
        raise ValueError("The selected case has no embedded LGR")
    sources = sources or {source: _numeric_keywords(case, source) for source in ("INIT", "UNRST")}
    records = records or {"INIT": [0], "UNRST": [0]}
    j_columns = list(range(lgr.get_dims()[1]))
    row_frames = []
    extraction_started = time.perf_counter()
    for source, keywords in sources.items():
        for keyword in keywords:
            for record in records[source]:
                for j_column in j_columns:
                    x_values, z_values, matrix, hover = _matrix(case, source, keyword, j_column, record, 1.0)
                    row_index, column_index = np.nonzero(np.isfinite(matrix))
                    row_frames.append(
                        pd.DataFrame(
                            {
                                "source": source,
                                "property": keyword,
                                "record": record,
                                "j_column": j_column,
                                "x": x_values[column_index],
                                "z": z_values[row_index],
                                "value": matrix[row_index, column_index],
                                "i": hover[row_index, column_index, 1],
                                "j": hover[row_index, column_index, 2],
                                "k": hover[row_index, column_index, 3],
                            }
                        )
                    )
    if timing is not None:
        timing["slice_extraction_and_rows"] = time.perf_counter() - extraction_started
    manifest = {
        "case": case_name,
        "sources": list(sources),
        "properties": sources,
        "j_columns": j_columns,
        "middle_j": lgr.get_dims()[1] // 2,
        "timesteps": [step for step in case.restart_timesteps if step["record"] in records["UNRST"]],
    }
    middle_slice = case.lgr_xz_slice(manifest["middle_j"])
    x_center = float(middle_slice["centers"][:, 0].mean())
    manifest["bounds"] = {
        "x_min": x_center - 10.0,
        "x_max": x_center + 10.0,
        "y_min": middle_slice["depth_min"],
        "y_max": middle_slice["depth_max"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_started = time.perf_counter()
    pd.concat(row_frames, ignore_index=True).to_parquet(output_dir / "data.parquet", index=False)
    if timing is not None:
        timing["parquet_write"] = time.perf_counter() - parquet_started
    manifest_started = time.perf_counter()
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    if timing is not None:
        timing["manifest_and_html_write"] = time.perf_counter() - manifest_started


def main() -> int:
    args = parse_args()
    timing: dict[str, float] = {}
    started = time.perf_counter()
    case = ResdataCase(args.results_root / args.case / "model" / "TEMP-0")
    timing["case_load"] = time.perf_counter() - started
    keyword_started = time.perf_counter()
    sources = {source: _numeric_keywords(case, source) for source in ("INIT", "UNRST")}
    timing["keyword_scan"] = time.perf_counter() - keyword_started
    records = {"INIT": [0], "UNRST": list(range(len(case.restart_timesteps))) if args.all_records else [0]}
    write_package(case, args.case, args.output_dir, timing, sources, records)
    timing["total"] = time.perf_counter() - started
    print(f"Wrote indexed WellViz package: {args.output_dir}")
    if args.timing:
        print("Timing:")
        for name, elapsed in timing.items():
            print(f"  {name}: {elapsed:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
