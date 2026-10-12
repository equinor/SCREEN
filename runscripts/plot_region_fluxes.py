#!/usr/bin/env python3
"""Plot exported region-to-region gas/water rates or totals from completed cases."""

from __future__ import annotations

import argparse
import json
import logging
import re
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray
from resdata.resfile import ResdataFile
from resdata.summary import Summary

VECTOR_PATTERN = re.compile(r"R[GW]F[RT]_([A-Z0-9]{1,3}):([1-9][0-9]*)-([1-9][0-9]*)")
LOGGER = logging.getLogger(__name__)


class RegionVector(NamedTuple):
    key: str
    partition: str
    source: int
    target: int


class Curve(NamedTuple):
    case_name: str
    vector: str
    unit: str
    dates: NDArray[np.datetime64]
    values: NDArray[np.float64]


def parse_vector(value: str) -> RegionVector:
    key = value.upper()
    match = VECTOR_PATTERN.fullmatch(key)
    if match is None:
        raise ValueError(f"Invalid region vector {value!r}; expected e.g. RGFR_LEG:1-6 or RGFT_HOL:1-2")
    suffix, source, target = match.groups()
    if source == target:
        raise ValueError(f"{key}: source and target regions must differ")
    return RegionVector(key, f"FIP{suffix}", int(source), int(target))


def discover_prefixes(root: Path, case_pattern: str, summary_stem: str | None) -> list[tuple[str, Path]]:
    if not root.is_dir():
        raise ValueError(f"Output root does not exist or is not a directory: {root}")
    cases = sorted(path for path in root.glob(case_pattern) if path.is_dir() and (path / "model").is_dir())
    if not cases:
        raise ValueError(f"No case directories with a model directory match {case_pattern!r} under {root}")
    prefixes = []
    for case in cases:
        stem = summary_stem
        metadata_path = case / "scenario.json"
        if stem is None and metadata_path.is_file():
            stem = json.loads(metadata_path.read_text(encoding="utf-8")).get("case_metadata", {}).get("case_stem")
        if stem is None:
            candidates = sorted((case / "model").glob("*.SMSPEC"))
            if len(candidates) != 1:
                raise ValueError(
                    f"{case.name}: expected one SMSPEC without case_metadata.case_stem, found {len(candidates)}; "
                    "select --summary-stem explicitly"
                )
            stem = candidates[0].stem
        if not isinstance(stem, str) or not stem or Path(stem).name != stem:
            raise ValueError(f"{case.name}: summary stem must be a file stem, not a path")
        prefix = case / "model" / stem
        for suffix in (".SMSPEC", ".UNSMRY", ".INIT"):
            path = Path(f"{prefix}{suffix}")
            if not path.is_file():
                raise ValueError(f"{case.name}: required output file not found: {path}")
        prefixes.append((case.name, prefix))
    return prefixes


def validate_regions(init: ResdataFile, vector: RegionVector, case_name: str) -> None:
    if vector.partition not in init:
        raise ValueError(f"{case_name}: {vector.partition} zonation was not found in INIT")
    # Include every occurrence, covering parent-grid and LGR zonations.
    regions: set[int] = set()
    for keyword in init[vector.partition]:
        regions.update(int(value) for value in keyword if value > 0)
    for region in (vector.source, vector.target):
        if region not in regions:
            raise ValueError(
                f"{case_name}: region {region} does not exist in {vector.partition}; "
                f"available regions: {sorted(regions)}"
            )


def available_vectors(
    prefixes: list[tuple[str, Path]], partition: str, quantity: str
) -> tuple[dict[str, Summary], dict[str, list[str]]]:
    summaries = {}
    availability: dict[str, list[str]] = {}
    keyword = f"{quantity}_{partition[3:]}"
    for case_name, prefix in prefixes:
        with closing(ResdataFile(f"{prefix}.INIT")) as init:
            if partition not in init:
                raise ValueError(f"{case_name}: {partition} zonation was not found in INIT")
            summary = read_summary(case_name, prefix)
            summaries[case_name] = summary
            for key in sorted(str(key) for key in summary.keys()):
                match = VECTOR_PATTERN.fullmatch(key)
                if match is None or key.split(":")[0] != keyword:
                    continue
                vector = parse_vector(key)
                validate_regions(init, vector, case_name)
                availability.setdefault(key, []).append(case_name)
    if not availability:
        raise ValueError(f"{partition} exists, but no {keyword} region-pair vectors were exported in the selected cases")
    return summaries, availability


def read_summary(case_name: str, prefix: Path) -> Summary:
    try:
        return Summary.load(smspec_file=f"{prefix}.SMSPEC", unsmry_file=f"{prefix}.UNSMRY")
    except OSError as exc:
        raise OSError(f"{case_name}: cannot load summary {prefix}: {exc}") from exc


def load_curves(
    prefixes: list[tuple[str, Path]],
    vectors: list[RegionVector],
    sign: int,
    summaries: dict[str, Summary] | None = None,
) -> list[Curve]:
    if sign not in (-1, 1):
        raise ValueError("Sign must be +1 or -1")
    curves = []
    units: dict[str, str] = {}
    for case_name, prefix in prefixes:
        with closing(ResdataFile(f"{prefix}.INIT")) as init:
            for vector in vectors:
                validate_regions(init, vector, case_name)
        summary = summaries[case_name] if summaries is not None else read_summary(case_name, prefix)
        dates = summary.numpy_dates
        if dates.size == 0 or np.isnat(dates).any() or np.any(dates[1:] < dates[:-1]):
            raise ValueError(f"{case_name}: summary dates are empty, invalid, or decreasing")
        for vector in vectors:
            if vector.key not in summary:
                raise ValueError(
                    f"{case_name}: {vector.partition} and regions {vector.source}, {vector.target} exist, "
                    f"but {vector.key} was not exported in the summary; no zero flow is assumed"
                )
            values = np.asarray(summary.numpy_vector(vector.key), dtype=np.float64) * sign
            if values.shape != dates.shape or not np.isfinite(values).all():
                raise ValueError(f"{case_name}: {vector.key} has invalid values or a date/vector length mismatch")
            unit = summary.unit(vector.key).strip()
            if not unit:
                raise ValueError(f"{case_name}: {vector.key} has no exported unit")
            if vector.key in units and unit != units[vector.key]:
                raise ValueError(f"{case_name}: {vector.key} unit {unit!r} differs from {units[vector.key]!r}")
            units[vector.key] = unit
            curves.append(Curve(case_name, vector.key, unit, dates.copy(), values))
    return curves


def plot_curves(curves: list[Curve], output: Path, sign: int, show: bool = False) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    keys = list(dict.fromkeys(curve.vector for curve in curves))
    if not keys:
        raise ValueError("No curves to plot")
    fig, axes = plt.subplots(len(keys), 1, squeeze=False, figsize=(10, 4 * len(keys)), sharex=True)
    try:
        for key, ax in zip(keys, axes[:, 0]):
            for curve in curves:
                if curve.vector == key:
                    ax.plot(curve.dates, curve.values, label=curve.case_name)
                    ax.set_ylabel(curve.unit)
            ax.set_title(f"{key} (exported values x {sign:+d})")
            ax.axhline(0, color="grey", linewidth=0.5)
            ax.grid(True, alpha=0.3)
            ax.legend()
        axes[-1, 0].set_xlabel("Simulation date")
        fig.autofmt_xdate()
        fig.tight_layout()
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
        if show:
            plt.show()
    finally:
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zonation", required=True, help="Exported FIP partition, e.g. FIPLEG or FIPHOL")
    parser.add_argument("--quantity", choices=("RGFR", "RWFR", "RGFT", "RWFT"), default="RGFR")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--list-vectors", action="store_true", help="List exported pair keys and case availability")
    selection.add_argument("--all", action="store_true", help="Plot all exported pairs for this zonation/quantity")
    selection.add_argument("--vector", action="append", help="Existing pair (1-2) or full key; repeat for multiple panels")
    parser.add_argument("--case-pattern", default="*", help="Case-directory glob, e.g. '*sheet*'")
    parser.add_argument("--summary-stem", help="Override the metadata stem; required for ambiguous legacy cases")
    parser.add_argument("--sign", type=int, choices=(-1, 1), default=1, help="Explicit sign multiplier; default preserves exported sign")
    parser.add_argument("--output", type=Path, help="Required when plotting, e.g. region_fluxes.png")
    parser.add_argument("--show", action="store_true", help="Also display the figure interactively")
    args = parser.parse_args()
    try:
        partition = args.zonation.upper()
        if re.fullmatch(r"FIP[A-Z0-9]{1,3}", partition) is None:
            raise ValueError("Zonation must be an exported FIP partition, e.g. FIPLEG or FIPHOL")
        if not args.list_vectors and args.output is None:
            raise ValueError("--output is required when plotting")
        prefixes = discover_prefixes(args.output_root, args.case_pattern, args.summary_stem)
        summaries, availability = available_vectors(prefixes, partition, args.quantity)
        if args.list_vectors:
            print(f"{partition} / {args.quantity}: exported vectors (direction as stored)")
            for key, cases in sorted(availability.items()):
                print(f"{key} | cases: {', '.join(cases)}")
            return
        selected = sorted(availability) if args.all else args.vector
        vectors = []
        for value in selected:
            key = value.upper() if ":" in value else f"{args.quantity}_{partition[3:]}:{value}"
            vector = parse_vector(key)
            if vector.partition != partition or key.split(":")[0] != f"{args.quantity}_{partition[3:]}":
                raise ValueError(f"{key} does not match --zonation {partition} and --quantity {args.quantity}")
            if key not in availability:
                for case_name, prefix in prefixes:
                    with closing(ResdataFile(f"{prefix}.INIT")) as init:
                        validate_regions(init, vector, case_name)
                raise ValueError(f"{key} was not exported; available vectors: {', '.join(sorted(availability))}")
            if vector not in vectors:
                vectors.append(vector)
        # --all uses each case's own exported pairs; missing pairs are not zero curves.
        curves = []
        for vector in vectors:
            exporting_cases = set(availability[vector.key])
            selected_prefixes = []
            for case_name, prefix in prefixes:
                if case_name in exporting_cases:
                    selected_prefixes.append((case_name, prefix))
                else:
                    LOGGER.warning("%s: %s was not exported; curve omitted (not assumed zero)", case_name, vector.key)
            curves.extend(load_curves(selected_prefixes, [vector], args.sign, summaries=summaries))
        plot_curves(curves, args.output, args.sign, args.show)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    print(f"Saved {args.output} ({len(prefixes)} cases, {len(vectors)} vectors)")


if __name__ == "__main__":
    main()
