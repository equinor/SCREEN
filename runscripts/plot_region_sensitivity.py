#!/usr/bin/env python3
"""Plot a recorded case input against a statistic of one region-pair rate."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import numpy as np

from src.GaP.libs.region_fluxes import Case, annual_mass_rate_scale, has_pair_regions, load_cases, select_vectors

LOGGER = logging.getLogger(__name__)


def summarize_rate(values: np.ndarray, statistic: str) -> float:
    """Return a statistic of absolute logged rates."""
    magnitude = np.abs(np.asarray(values, dtype=float))
    if magnitude.size == 0 or not np.isfinite(magnitude).all():
        raise ValueError("rate vector must contain finite values")
    if statistic == "last":
        return float(magnitude[-1])
    if statistic == "min":
        return float(np.min(magnitude))
    if statistic == "max":
        return float(np.max(magnitude))
    if statistic == "mean":
        return float(np.mean(magnitude))
    raise ValueError(f"unknown rate statistic {statistic!r}")


def sensitivity_rows(cases: list[Case], key: str, parameter: str, statistic: str, zonation: str) -> list[tuple[Case, float, float]]:
    rows = []
    for case in cases:
        if not has_pair_regions(case.regions, key):
            LOGGER.warning("%s: %s requires regions not present in %s; skipping case", case.name, key, zonation)
            continue
        if key not in case.keys:
            LOGGER.warning("%s: %s not logged; skipping case", case.name, key)
            continue
        if case.unit != "kg/day":
            raise ValueError(f"{case.name}: sensitivity plots require mass-rate cases in kg/day, got {case.unit!r}")
        parameter_value = case.inputs.get(parameter) if case.inputs else None
        if isinstance(parameter_value, bool) or not isinstance(parameter_value, (int, float)) or not np.isfinite(parameter_value):
            raise ValueError(f"{case.name}: missing or invalid recorded parameter {parameter!r}")
        dates = case.summary.numpy_dates
        values = np.asarray(case.summary.numpy_vector(key), dtype=float)
        if dates.size == 0 or np.isnat(dates).any() or values.shape != dates.shape or not np.isfinite(values).all():
            raise ValueError(f"{case.name}: invalid dates/vector length for {key}")
        rate = summarize_rate(values * case.scale, statistic)
        rows.append((case, float(parameter_value), rate))
    if not rows:
        raise ValueError(f"No selected cases logged {key}")
    return sorted(rows, key=lambda row: (row[1], row[0].name))


def plot_sensitivity(
    rows: list[tuple[Case, float, float]], key: str, parameter: str, statistic: str,
    reference_case: str | None, output: Path, show: bool, xscale: str, yscale: str,
    xlabel: str | None, figsize: tuple[float, float], dpi: int | None,
) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from src.WellClass.libs.plotting import screen_style

    if xscale == "log" and any(value <= 0 for _, value, _ in rows):
        raise ValueError("Logarithmic x-axis requires positive parameter values")
    if yscale == "log" and any(rate <= 0 for _, _, rate in rows):
        raise ValueError("Logarithmic y-axis requires positive rates; use a different statistic or linear y-scale")
    value_scale, ylabel = annual_mass_rate_scale([np.asarray([rate]) for _, _, rate in rows])
    style = screen_style()
    if dpi is not None:
        style["figure.dpi"] = dpi
    with plt.rc_context(style):
        fig, ax = plt.subplots(figsize=figsize, layout="constrained")
        try:
            sensitivity = [row for row in rows if row[0].name != reference_case]
            reference = [row for row in rows if row[0].name == reference_case]
            if sensitivity:
                ax.scatter(
                    [row[1] for row in sensitivity], [row[2] * value_scale for row in sensitivity],
                    color="tab:blue", marker="o", label="Sensitivity", zorder=2,
                )
            if reference:
                ax.scatter(
                    [row[1] for row in reference], [row[2] * value_scale for row in reference],
                    color="black", marker="D", label="Reference", zorder=3,
                )
            ax.set(
                xlabel=xlabel or parameter.replace("_", " "),
                ylabel=f"{statistic.capitalize()} rate magnitude ({ylabel})",
                title=key,
                xscale=xscale,
                yscale=yscale,
            )
            ax.grid(True, alpha=0.3)
            ax.legend()
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
    parser.add_argument("--quantity", choices=("RGFR", "RWFR"), default="RGFR")
    parser.add_argument("--vector", required=True, help="Region pair, e.g. 1-6, or full summary key")
    parser.add_argument("--x-parameter", required=True, help="Recorded scalar from scenario.json or grid_policy.json")
    parser.add_argument("--case-pattern", default="*", help="Case-directory glob")
    parser.add_argument("--reference-case", help="Reference directory name under output-root; plotted in black")
    parser.add_argument("--summary-stem", help="Override the metadata stem for ambiguous legacy cases")
    parser.add_argument("--rate-stat", choices=("last", "min", "max", "mean"), default="last")
    parser.add_argument("--x-label", help="X-axis label; defaults to the parameter name")
    parser.add_argument("--x-scale", choices=("linear", "log"), default="linear")
    parser.add_argument("--y-scale", choices=("linear", "log"), default="linear")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--figsize", type=float, nargs=2, metavar=("WIDTH", "HEIGHT"), default=(8, 5))
    parser.add_argument("--dpi", type=int)
    args = parser.parse_args()
    try:
        if re.fullmatch(r"FIP[A-Z0-9]{1,3}", args.zonation) is None:
            raise ValueError("Zonation must be an exported FIP partition, e.g. FIPLEG or FIPHOL")
        if min(args.figsize) <= 0:
            raise ValueError("--figsize width and height must be positive")
        if args.dpi is not None and args.dpi <= 0:
            raise ValueError("--dpi must be positive")
        cases = load_cases(
            args.output_root, args.zonation, args.quantity, args.case_pattern, args.summary_stem,
            mass=True, reference_case=args.reference_case,
        )
        key = select_vectors(cases, args.zonation, args.quantity, [args.vector])[0]
        rows = sensitivity_rows(cases, key, args.x_parameter, args.rate_stat, args.zonation)
        plot_sensitivity(
            rows, key, args.x_parameter, args.rate_stat, args.reference_case,
            args.output, args.show, args.x_scale, args.y_scale, args.x_label,
            tuple(args.figsize), args.dpi,
        )
        print(f"Saved {args.output} ({len(rows)} cases, {key}, {args.rate_stat} rate)")
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
