from functools import lru_cache
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

from ..well_pressure import Pressure
from .plot_sketch import plot_sketch

DEFAULT_FONT_DIR = Path(__file__).resolve().parents[4] / "notebooks" / "Equinor_regular"


@lru_cache(maxsize=None)
def _register_fonts(font_dir: str) -> bool:
    fonts = font_manager.findSystemFonts(fontpaths=font_dir) if Path(font_dir).is_dir() else []
    for font_file in fonts:
        font_manager.fontManager.addfont(font_file)
    return bool(fonts)


def screen_style(font_dir: Optional[Path] = None, *, dpi: int = 200, font_size: float = 9) -> dict:
    """Return SCREEN rcParams, registering the Equinor fonts when they are available."""
    style = {"figure.dpi": dpi, "font.size": font_size}
    if _register_fonts(str(font_dir or DEFAULT_FONT_DIR)):
        style["font.family"] = "Equinor"
    return style


def _fit_pressure_axis(ax, z_bottom: float) -> None:
    """Scale the x axis to the pressure lines within the visible depth interval."""
    values = []
    for line in ax.get_lines():
        depth, pressure = np.asarray(line.get_ydata(), dtype=float), np.asarray(line.get_xdata(), dtype=float)
        # interpolate onto the cut depth so lines ending beyond it still reach the frame edge
        visible = (depth >= 0) & (depth <= z_bottom)
        values.extend(pressure[visible])
        if depth.size > 1 and depth.min() < z_bottom < depth.max():
            order = np.argsort(depth)
            values.append(float(np.interp(z_bottom, depth[order], pressure[order])))
    if values:
        lo, hi = min(values), max(values)
        margin = 0.05 * (hi - lo or 1.0)
        ax.set_xlim(lo - margin, hi + margin)


def plot_one_page(
    well,
    pressure: Pressure,
    scenario_name: str = "default",
    *,
    title: str = "WellClass one-page QC",
    figsize: tuple = (12, 8),
    sketch_kwargs: Optional[dict] = None,
    casing_hole=None,
    depth_buffer: Optional[float] = 100.0,
    style: Optional[dict] = None,
):
    """Plot a WellProcessed sketch beside the pressure profiles of one Pressure scenario.

    ``casing_hole`` (a CasingHole, e.g. ``scenario.casing_hole``) marks the hole on the sketch.
    The depth axis runs from the surface to the scenario's ``z_fluid_datum`` plus ``depth_buffer`` metres
    (clamped to the table depth); pass ``depth_buffer=None`` to show the full table depth. The pressure
    axis is scaled to the visible interval.
    Returns ``fig, (ax_well, ax_pressure)`` without showing the figure, so callers can add overlays.
    """
    scenario = pressure.scenarios[scenario_name]
    table = scenario.table
    curves = scenario.display_curves()

    max_depth = float(table.depth.max())
    z_bottom = max_depth
    if depth_buffer is not None and scenario.z_fluid_datum is not None:
        z_bottom = min(max_depth, float(scenario.z_fluid_datum) + depth_buffer)

    with plt.rc_context(style if style is not None else screen_style()):
        fig, (ax_well, ax_pressure) = plt.subplots(1, 2, figsize=figsize, sharey=True)
        plot_sketch(well, ax=ax_well, **{**(sketch_kwargs or {}), **({"casing_hole": casing_hole} if casing_hole is not None else {})})
        ax_well.set_title("WellClass sketch")

        ax_pressure.plot(table.hydrostatic_pressure, table.depth, color="steelblue", linestyle=":", label="hydrostatic water")
        ax_pressure.plot(table.min_horizontal_stress, table.depth, color="gray", linestyle="--", label="Shmin")
        ax_pressure.plot(curves["brine_pressure"], curves["brine_depth"], color="steelblue", label=f"{scenario_name} brine")
        ax_pressure.plot(curves["fluid_pressure"], curves["fluid_depth"], color="firebrick", label=f"{scenario_name} CO2")

        ax_pressure.set_title("Pressure profiles (Pressure class)")
        ax_pressure.set_xlabel("pressure [bar]")
        ax_pressure.set_ylim(z_bottom, 0)
        if z_bottom < max_depth:
            _fit_pressure_axis(ax_pressure, z_bottom)
        ax_pressure.grid(alpha=0.25)
        ax_pressure.legend()

        # with wspace=0, panels butt together, so only the leftmost keeps the shared y axis
        ax_pressure.set_ylabel("")
        ax_pressure.tick_params(labelleft=False)

        fig.suptitle(title)
        fig.tight_layout()
        fig.subplots_adjust(wspace=0)

    return fig, (ax_well, ax_pressure)
