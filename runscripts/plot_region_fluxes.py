#!/usr/bin/env python3
"""List and plot region-pair rates/totals from completed CIRRUS 1.9 cases."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import numpy as np
from src.GaP.libs.region_fluxes import (
    Case,
    annual_mass_rate_scale,
    has_pair_regions,
    load_cases,
    select_vectors,
)

LOGGER = logging.getLogger(__name__)


def case_labels(cases: list[Case], mode: str) -> tuple[list[Case], list[str], str | None]:
    """Cases, legend labels and legend title; "changed" labels only the inputs that differ, sorted by them."""
    names = [case.name for case in cases]
    if mode != "changed":
        return cases, names, None
    if len(cases) < 2 or not all(case.inputs for case in cases):
        LOGGER.warning("changed-input labels need scenario.json in every case and at least two cases; using case names")
        return cases, names, None
    fields = dict.fromkeys(key for case in cases for key in case.inputs)
    varying = [key for key in fields if len({repr(case.inputs.get(key)) for case in cases}) > 1]
    if not varying:
        LOGGER.warning("no recorded input differs between the cases; using case names")
        return cases, names, None

    def order(case: Case) -> tuple:
        values = [case.inputs.get(key) for key in varying]
        return tuple(
            (2, "") if value is None else (0, value) if isinstance(value, (int, float)) and not isinstance(value, bool) else (1, str(value))
            for value in values
        )

    cases = sorted(cases, key=order)

    def short(key: str) -> str:
        return key.replace("casing_hole_", "hole_")

    def fmt(value: object) -> str:
        if value is None:
            return "default"
        return f"{value:g}" if isinstance(value, float) else str(value)

    labels = [", ".join(f"{short(key)}={fmt(case.inputs.get(key))}" for key in varying) for case in cases]
    return cases, labels, "Varied: " + ", ".join(short(key) for key in varying)


def plot_fluxes(
    cases: list[Case], keys: list[str], zonation: str, sign: int, output: Path, show: bool,
    label_mode: str = "case", reference_case: str | None = None,
    figsize: tuple[float, float] | None = None, dpi: int | None = None,
) -> None:
    """Plot the selected vectors; figsize is (width, height) in inches and defaults to a size scaled to the panels and cases."""
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.lines import Line2D

    from src.WellClass.libs.plotting import screen_style

    curves = []
    plotted_cases: dict[str, Case] = {}
    for key in keys:
        for case in cases:
            if not has_pair_regions(case.regions, key):
                LOGGER.warning("%s: %s requires regions not present in %s; skipping case", case.name, key, zonation)
                continue
            dates = case.summary.numpy_dates
            missing = key not in case.keys
            values = np.zeros(dates.shape) if missing else np.asarray(case.summary.numpy_vector(key), dtype=float) * sign * case.scale
            if values.shape != dates.shape or not np.isfinite(values).all():
                raise ValueError(f"{case.name}: {key} has invalid values or a date/vector length mismatch")
            if missing:
                LOGGER.warning("%s: %s omitted by CIRRUS 1.9; zero direct transfer inferred", case.name, key)
            curves.append((key, case, dates, values, missing))
            plotted_cases[case.name] = case
    ordered, labels, legend_title = case_labels(list(plotted_cases.values()), label_mode)
    label_of = {case.name: label for case, label in zip(ordered, labels)}
    if len(ordered) <= 10:
        palette = plt.get_cmap("tab10").colors
    else:
        palette = [plt.get_cmap("turbo")(index / (len(ordered) - 1)) for index in range(len(ordered))]
    color_of = {case.name: palette[index % len(palette)] for index, case in enumerate(ordered)}
    if reference_case is not None:
        color_of[reference_case] = "black"
        label_of[reference_case] += " (reference)"
    style = screen_style()
    if dpi is not None:
        style["figure.dpi"] = dpi
    if figsize is None:
        figsize = (10, max(4 * len(keys), 0.3 * len(cases) + 1))
    with plt.rc_context(style):
        width_of = {
            case.name: (2.0 if case.name == reference_case else 1.0) if reference_case is not None else plt.rcParams["lines.linewidth"]
            for case in ordered
        }
        fig, axes = plt.subplots(
            len(keys), 1, squeeze=False, figsize=figsize, sharex=True, layout="constrained"
        )
        try:
            for key, ax in zip(keys, axes[:, 0]):
                key_curves = [curve for curve in curves if curve[0] == key]
                if cases[0].unit == "kg/day":
                    value_scale, ylabel = annual_mass_rate_scale([curve[3] for curve in key_curves])
                else:
                    value_scale, ylabel = 1.0, cases[0].unit
                for curve_key, case, dates, values, missing in key_curves:
                    label = f"{label_of[case.name]} (inferred zero)" if missing else label_of[case.name]
                    ax.plot(
                        dates, values * value_scale, label=label, linestyle="--" if missing else "-", color=color_of[case.name],
                        linewidth=width_of[case.name], zorder=3 if case.name == reference_case else 2,
                    )
                ax.set(title=f"{key} (sign multiplier {sign:+d})", ylabel=ylabel)
                ax.grid(True, alpha=0.3)
            axes[-1, 0].set_xlabel("Simulation date")
            handles = [
                Line2D([], [], color=color_of[case.name], linewidth=width_of[case.name], label=label_of[case.name])
                for case in ordered
            ]
            if any(curve[4] for curve in curves):
                handles.append(Line2D([], [], color="black", linestyle="--", label="inferred zero (pair not exported)"))
            fig.legend(handles=handles, loc="outside right center", title=legend_title)
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
    parser.add_argument("--reference-case", help="Case directory name under output-root; included regardless of pattern and plotted in black")
    parser.add_argument("--summary-stem", help="Override the metadata stem for ambiguous legacy cases")
    parser.add_argument("--sign", type=int, choices=(-1, 1), default=1)
    parser.add_argument("--output", type=Path, help="Plot filename; required when plotting")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--figsize", type=float, nargs=2, metavar=("WIDTH", "HEIGHT"), help="Figure size in inches; default scales with panels and cases")
    parser.add_argument("--dpi", type=int, help="Figure resolution; default is the SCREEN style (200)")
    parser.add_argument(
        "--label-mode",
        choices=("case", "changed"),
        default="case",
        help="Legend labels: the case name, or only the recorded inputs that differ between the plotted cases",
    )
    parser.add_argument("--volume", action="store_true", help="Keep gas/water volumes; default converts them to mass using the matching EOS surface density")
    args = parser.parse_args()
    try:
        if re.fullmatch(r"FIP[A-Z0-9]{1,3}", args.zonation) is None:
            raise ValueError("Zonation must be an exported FIP partition, e.g. FIPLEG or FIPHOL")
        if not args.list_vectors and args.output is None:
            raise ValueError("--output is required when plotting")
        if args.figsize is not None and min(args.figsize) <= 0:
            raise ValueError("--figsize width and height must be positive")
        if args.dpi is not None and args.dpi <= 0:
            raise ValueError("--dpi must be positive")
        cases = load_cases(
            args.output_root, args.zonation, args.quantity, args.case_pattern, args.summary_stem,
            mass=not args.volume and not args.list_vectors,
            reference_case=args.reference_case,
        )
        keys = select_vectors(cases, args.zonation, args.quantity, args.vector)
        if args.list_vectors:
            for key in keys:
                print(f"{key} | cases: {', '.join(case.name for case in cases if key in case.keys)}")
        else:
            plot_fluxes(cases, keys, args.zonation, args.sign, args.output, args.show, args.label_mode, args.reference_case,
                        tuple(args.figsize) if args.figsize else None, args.dpi)
            print(f"Saved {args.output} ({len(cases)} cases, {len(keys)} vectors)")
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
