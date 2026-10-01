from functools import lru_cache
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
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


def plot_one_page(
    well,
    pressure: Pressure,
    scenario_name: str = "default",
    *,
    title: str = "WellClass one-page QC",
    figsize: tuple = (12, 8),
    sketch_kwargs: Optional[dict] = None,
    style: Optional[dict] = None,
):
    """Plot a WellProcessed sketch beside the pressure profiles of one Pressure scenario.

    Returns ``fig, (ax_well, ax_pressure)`` without showing the figure, so callers can add overlays.
    """
    scenario = pressure.scenarios[scenario_name]
    table = scenario.table
    curves = scenario.display_curves()

    with plt.rc_context(style if style is not None else screen_style()):
        fig, (ax_well, ax_pressure) = plt.subplots(1, 2, figsize=figsize, sharey=True)
        plot_sketch(well, ax=ax_well, **(sketch_kwargs or {}))
        ax_well.set_title("WellClass sketch")

        ax_pressure.plot(table.hydrostatic_pressure, table.depth, color="steelblue", linestyle=":", label="hydrostatic water")
        ax_pressure.plot(table.min_horizontal_stress, table.depth, color="gray", linestyle="--", label="Shmin")
        ax_pressure.plot(curves["brine_pressure"], curves["brine_depth"], color="steelblue", label=f"{scenario_name} brine")
        ax_pressure.plot(curves["fluid_pressure"], curves["fluid_depth"], color="firebrick", label=f"{scenario_name} CO2")

        ax_pressure.set_title("Pressure profiles (Pressure class)")
        ax_pressure.set_xlabel("pressure [bar]")
        ax_pressure.set_ylim(0, float(table.depth.max()))
        ax_pressure.invert_yaxis()
        ax_pressure.grid(alpha=0.25)
        ax_pressure.legend()

        # with wspace=0, panels butt together, so only the leftmost keeps the shared y axis
        ax_pressure.set_ylabel("")
        ax_pressure.tick_params(labelleft=False)

        fig.suptitle(title)
        fig.tight_layout()
        fig.subplots_adjust(wspace=0)

    return fig, (ax_well, ax_pressure)
