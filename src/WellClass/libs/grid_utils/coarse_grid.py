import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CoarseGridSpec:
    """Explicit vertical assumptions for a coarse grid recipe.

    Depths use the same positive-downward MSL convention as GaP grid inputs.
    The specification describes the domain; it does not write simulator files.
    """

    top_depth: float
    water_depth: float
    reservoir_top: float
    bottom_depth: float
    water_layers: int = 1
    overburden_layers: int = 9
    reservoir_layers: int = 50

    def __post_init__(self):
        depths = (self.top_depth, self.water_depth, self.reservoir_top, self.bottom_depth)
        if not all(math.isfinite(depth) for depth in depths):
            raise ValueError("coarse-grid depths must be finite")
        if not self.top_depth < self.water_depth < self.reservoir_top < self.bottom_depth:
            raise ValueError("coarse-grid depths must satisfy top < water < reservoir top < bottom")
        layers = (self.water_layers, self.overburden_layers, self.reservoir_layers)
        if not all(isinstance(count, int) and count > 0 for count in layers):
            raise ValueError("coarse-grid layer counts must be positive integers")


@dataclass(frozen=True)
class VerticalGridSchedule:
    """Vertical cell thicknesses and their physical section labels."""

    dz: np.ndarray
    sections: tuple[str, ...]

    @property
    def depth_edges(self) -> np.ndarray:
        return np.concatenate(([0.0], np.cumsum(self.dz)))


def build_vertical_grid_schedule(spec: CoarseGridSpec, well=None) -> VerticalGridSchedule:
    """Build an evenly distributed vertical coarse-grid schedule.

    ``well`` may be a ``WellProcessed`` instance. When supplied, its deepest
    derived borehole interval must be covered by ``spec.bottom_depth``.
    """

    if well is not None:
        borehole = getattr(well, "borehole", None) or []
        well_top = min((float(record["top_tvd_msl"]) for record in borehole), default=spec.top_depth)
        well_bottom = max((float(record["bottom_tvd_msl"]) for record in borehole), default=spec.top_depth)
        if well_top < spec.top_depth:
            raise ValueError(f"coarse-grid top {spec.top_depth} does not cover well top {well_top}")
        if well_bottom > spec.bottom_depth:
            raise ValueError(f"coarse-grid bottom {spec.bottom_depth} does not cover well bottom {well_bottom}")

    thicknesses = np.array(
        [
            (spec.water_depth - spec.top_depth) / spec.water_layers,
            (spec.reservoir_top - spec.water_depth) / spec.overburden_layers,
            (spec.bottom_depth - spec.reservoir_top) / spec.reservoir_layers,
        ]
    )
    counts = (spec.water_layers, spec.overburden_layers, spec.reservoir_layers)
    dz = np.concatenate([np.full(count, thickness) for count, thickness in zip(counts, thicknesses)])
    sections = ("water",) * spec.water_layers + ("overburden",) * spec.overburden_layers + ("reservoir",) * spec.reservoir_layers
    return VerticalGridSchedule(dz=dz, sections=sections)
