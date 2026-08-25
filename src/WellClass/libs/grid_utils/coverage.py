from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .coarse_grid import CoarseGridEnvelope


@dataclass(frozen=True)
class GridCoverageReport:
    """Coverage result comparing a required well envelope with grid bounds."""

    required: CoarseGridEnvelope
    grid_x_min: float
    grid_x_max: float
    grid_y_min: float
    grid_y_max: float
    grid_z_min: float
    grid_z_max: float
    missing_x_min: float
    missing_x_max: float
    missing_y_min: float
    missing_y_max: float
    missing_z_min: float
    missing_z_max: float
    cell_size_min: float | None = None
    cell_size_max: float | None = None
    warnings: tuple[str, ...] = ()

    @property
    def covered(self) -> bool:
        return not any(
            (
                self.missing_x_min,
                self.missing_x_max,
                self.missing_y_min,
                self.missing_y_max,
                self.missing_z_min,
                self.missing_z_max,
            )
        )


def assess_grid_coverage(
    required: CoarseGridEnvelope,
    *,
    grid_x_min: float,
    grid_x_max: float,
    grid_y_min: float,
    grid_y_max: float,
    grid_z_min: float,
    grid_z_max: float,
    cell_sizes: Sequence[float] | None = None,
) -> GridCoverageReport:
    """Report whether grid bounds cover a required well envelope."""

    bounds = (grid_x_min, grid_x_max, grid_y_min, grid_y_max, grid_z_min, grid_z_max)
    if not all(math.isfinite(float(bound)) for bound in bounds):
        raise ValueError("grid bounds must be finite")
    if not grid_x_min <= grid_x_max or not grid_y_min <= grid_y_max or not grid_z_min <= grid_z_max:
        raise ValueError("grid bounds must be ordered")

    cell_size_min = cell_size_max = None
    if cell_sizes is not None:
        values = [float(size) for size in cell_sizes]
        if not values or not all(math.isfinite(size) and size > 0 for size in values):
            raise ValueError("cell_sizes must contain positive finite values")
        cell_size_min = min(values)
        cell_size_max = max(values)

    missing = (
        max(0.0, grid_x_min - required.x_min),
        max(0.0, required.x_max - grid_x_max),
        max(0.0, grid_y_min - required.y_min),
        max(0.0, required.y_max - grid_y_max),
        max(0.0, grid_z_min - required.z_min),
        max(0.0, required.z_max - grid_z_max),
    )
    warnings = tuple(
        f"grid is missing {amount:g} m at {direction}"
        for direction, amount in zip(("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"), missing)
        if amount > 0
    )
    return GridCoverageReport(
        required=required,
        grid_x_min=grid_x_min,
        grid_x_max=grid_x_max,
        grid_y_min=grid_y_min,
        grid_y_max=grid_y_max,
        grid_z_min=grid_z_min,
        grid_z_max=grid_z_max,
        missing_x_min=missing[0],
        missing_x_max=missing[1],
        missing_y_min=missing[2],
        missing_y_max=missing[3],
        missing_z_min=missing[4],
        missing_z_max=missing[5],
        cell_size_min=cell_size_min,
        cell_size_max=cell_size_max,
        warnings=warnings,
    )
