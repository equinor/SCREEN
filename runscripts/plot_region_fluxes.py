#!/usr/bin/env python3
"""List and plot region-pair rates/totals from completed CIRRUS 1.9 cases."""

from __future__ import annotations

import argparse
import json
import logging
import re
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

import numpy as np
from resdata.resfile import ResdataFile
from resdata.summary import Summary

LOGGER = logging.getLogger(__name__)


class Case(NamedTuple):
    name: str
    summary: Summary
    regions: set[int]
    keys: set[str]
    unit: str


def check_regions(case_name: str, regions: set[int], zonation: str, key: str) -> None:
    for region in map(int, key.split(":")[1].split("-")):
        if region not in regions:
            raise ValueError(f"{case_name}: region {region} does not exist in {zonation}; available regions: {sorted(regions)}")


def load_cases(root: Path, zonation: str, quantity: str, pattern: str, stem: str | None) -> list[Case]:
    keyword = f"{quantity}_{zonation[3:]}"
    pair_pattern = re.compile(rf"{keyword}:([1-9][0-9]*)-([1-9][0-9]*)")
    cases = []
    for directory in sorted(root.glob(pattern)):
        model = directory / "model"
        if not model.is_dir():
            continue
        case_stem = stem
        metadata = directory / "scenario.json"
        if case_stem is None and metadata.is_file():
            case_stem = json.loads(metadata.read_text(encoding="utf-8")).get("case_metadata", {}).get("case_stem")
        if case_stem is None:
            candidates = sorted(model.glob("*.SMSPEC"))
            if len(candidates) != 1:
                raise ValueError(f"{directory.name}: expected one SMSPEC, found {len(candidates)}; use --summary-stem")
            case_stem = candidates[0].stem
        if not isinstance(case_stem, str) or not case_stem or Path(case_stem).name != case_stem:
            raise ValueError(f"{directory.name}: summary stem must be a file stem, not a path")
        prefix = model / case_stem
        for suffix in (".SMSPEC", ".UNSMRY", ".INIT"):
            if not Path(f"{prefix}{suffix}").is_file():
                raise ValueError(f"{directory.name}: required output file not found: {prefix}{suffix}")
        with closing(ResdataFile(f"{prefix}.INIT")) as init:
            if zonation not in init:
                raise ValueError(f"{directory.name}: {zonation} zonation was not found in INIT")
            regions = {int(value) for array in init[zonation] for value in array if value > 0}
        try:
            summary = Summary.load(smspec_file=f"{prefix}.SMSPEC", unsmry_file=f"{prefix}.UNSMRY")
        except OSError as exc:
            raise OSError(f"{directory.name}: cannot load summary {prefix}: {exc}") from exc
        keys = {str(key) for key in summary.keys() if pair_pattern.fullmatch(str(key))}
        if not keys:
            raise ValueError(f"{directory.name}: {zonation} exists, but no {keyword} pair vectors confirm reporting")
        for key in keys:
            check_regions(directory.name, regions, zonation, key)
        units = {summary.unit(key).strip() for key in keys}
        if len(units) != 1 or not next(iter(units)):
            raise ValueError(f"{directory.name}: inconsistent or missing units for {keyword}")
        unit = units.pop()
        if cases and unit != cases[0].unit:
            raise ValueError(f"{directory.name}: unit {unit!r} differs from {cases[0].unit!r}")
        dates = summary.numpy_dates
        if dates.size == 0 or np.isnat(dates).any() or np.any(dates[1:] < dates[:-1]):
            raise ValueError(f"{directory.name}: summary dates are empty, invalid, or decreasing")
        cases.append(Case(directory.name, summary, regions, keys, unit))
    if not cases:
        raise ValueError(f"No case directories with a model directory match {pattern!r} under {root}")
    return cases


def select_vectors(cases: list[Case], zonation: str, quantity: str, requested: list[str] | None) -> list[str]:
    available = set().union(*(case.keys for case in cases))
    if requested is None:
        return sorted(available)
    keyword = f"{quantity}_{zonation[3:]}"
    selected = []
    for value in requested:
        key = value.upper() if ":" in value else f"{keyword}:{value}"
        match = re.fullmatch(rf"{keyword}:([1-9][0-9]*)-([1-9][0-9]*)", key)
        if match is None or match[1] == match[2]:
            raise ValueError(f"Invalid pair {value!r}; expected e.g. 1-2 or {keyword}:1-2")
        for case in cases:
            check_regions(case.name, case.regions, zonation, key)
        if key not in available:
            raise ValueError(f"{key} was not exported; available vectors: {', '.join(sorted(available))}")
        if key not in selected:
            selected.append(key)
    return selected


def plot_fluxes(cases: list[Case], keys: list[str], zonation: str, sign: int, output: Path, show: bool) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    curves = []
    for key in keys:
        for case in cases:
            check_regions(case.name, case.regions, zonation, key)
            dates = case.summary.numpy_dates
            missing = key not in case.keys
            values = np.zeros(dates.shape) if missing else np.asarray(case.summary.numpy_vector(key), dtype=float) * sign
            if values.shape != dates.shape or not np.isfinite(values).all():
                raise ValueError(f"{case.name}: {key} has invalid values or a date/vector length mismatch")
            if missing:
                LOGGER.warning("%s: %s omitted by CIRRUS 1.9; zero direct transfer inferred", case.name, key)
            curves.append((key, case, dates, values, missing))
    fig, axes = plt.subplots(len(keys), 1, squeeze=False, figsize=(10, 4 * len(keys)), sharex=True)
    try:
        for key, ax in zip(keys, axes[:, 0]):
            for curve_key, case, dates, values, missing in curves:
                if curve_key == key:
                    label = f"{case.name} (inferred zero)" if missing else case.name
                    ax.plot(dates, values, label=label, linestyle="--" if missing else "-")
            ax.set(title=f"{key} (sign multiplier {sign:+d})", ylabel=cases[0].unit)
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
    parser.add_argument("--zonation", type=str.upper, required=True, help="FIPLEG, FIPHOL, or another exported FIP partition")
    parser.add_argument("--quantity", choices=("RGFR", "RWFR", "RGFT", "RWFT"), default="RGFR")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--list-vectors", action="store_true")
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--vector", action="append", help="Existing pair or full key; repeat for multiple panels")
    parser.add_argument("--case-pattern", default="*", help="Case-directory glob")
    parser.add_argument("--summary-stem", help="Override the metadata stem for ambiguous legacy cases")
    parser.add_argument("--sign", type=int, choices=(-1, 1), default=1)
    parser.add_argument("--output", type=Path, help="Plot filename; required when plotting")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    try:
        if re.fullmatch(r"FIP[A-Z0-9]{1,3}", args.zonation) is None:
            raise ValueError("Zonation must be an exported FIP partition, e.g. FIPLEG or FIPHOL")
        if not args.list_vectors and args.output is None:
            raise ValueError("--output is required when plotting")
        cases = load_cases(args.output_root, args.zonation, args.quantity, args.case_pattern, args.summary_stem)
        keys = select_vectors(cases, args.zonation, args.quantity, args.vector)
        if args.list_vectors:
            for key in keys:
                print(f"{key} | cases: {', '.join(case.name for case in cases if key in case.keys)}")
        else:
            plot_fluxes(cases, keys, args.zonation, args.sign, args.output, args.show)
            print(f"Saved {args.output} ({len(cases)} cases, {len(keys)} vectors)")
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
