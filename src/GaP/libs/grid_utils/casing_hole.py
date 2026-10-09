from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite, pi
from typing import TextIO

import numpy as np
import pandas as pd
from resdata.grid import Grid

from src.GaP.libs.models.casing_hole import CasingHole


@dataclass(frozen=True)
class HoleFace:
    i: int
    j: int
    k: int
    face_area_m2: float
    opening_area_m2: float
    multiplier: float


def refined_depth_edges(grid: Grid, i: int, j: int, subdivisions: np.ndarray, first_k: int = 0) -> np.ndarray:
    """Absolute layer boundaries for the supported flat, contiguous grid column."""
    edges = []
    reference_xy = None
    for k, count in enumerate(subdivisions, start=first_k):
        coordinates = np.asarray([grid.get_cell_corner(corner, ijk=(i, j, k)) for corner in range(8)])
        if reference_xy is None:
            reference_xy = coordinates[:4, :2]
            x0, y0 = reference_xy[0]
            x1, y1 = reference_xy[3]
            if x1 <= x0 or y1 <= y0 or not np.allclose(
                reference_xy, [[x0, y0], [x1, y0], [x0, y1], [x1, y1]], rtol=0, atol=1e-8
            ):
                raise ValueError("casing holes require an axis-aligned Cartesian grid")
        corners = coordinates[:, 2]
        top, bottom = corners[0], corners[4]
        if (
            not np.isfinite(corners).all()
            or bottom <= top
            or not np.allclose(corners[:4], top, rtol=0, atol=1e-8)
            or not np.allclose(corners[4:], bottom, rtol=0, atol=1e-8)
            or (edges and not isclose(edges[-1], top, rel_tol=0, abs_tol=1e-8))
            or not np.allclose(coordinates[:4, :2], reference_xy, rtol=0, atol=1e-8)
            or not np.allclose(coordinates[4:, :2], reference_xy, rtol=0, atol=1e-8)
        ):
            raise ValueError("casing holes require flat, contiguous coarse-grid layers with a constant vertical footprint")
        if not np.isfinite(count) or count < 1 or int(count) != count:
            raise ValueError("casing hole refinement counts must be positive integers")
        if not edges:
            edges.append(top)
        edges.extend(np.linspace(top, bottom, int(count) + 1)[1:])
    return np.asarray(edges)


def resolve_casing_hole(
    hole: CasingHole,
    casings: pd.DataFrame,
    depth_edges: np.ndarray,
    widths_y: np.ndarray,
    nx: int,
) -> tuple[HoleFace, ...]:
    """Allocate circular area center-out on one +X interface, without changing K."""
    hole.validate_casing(
        (row["name"], float(row["top_msl"]), float(row["bottom_msl"]))
        for _, row in casings.iterrows()
    )
    if (
        len(depth_edges) < 2
        or not np.isfinite(depth_edges).all()
        or not (np.diff(depth_edges) > 0).all()
        or not np.isfinite(widths_y).all()
        or not (widths_y > 0).all()
    ):
        raise ValueError("casing hole grid dimensions must be finite and positive")
    row = casings.loc[casings["name"] == hole.casing].iloc[0]
    k = int(np.searchsorted(depth_edges, hole.depth_mTVDMSL, side="right") - 1)
    i, j_min, j_max = (int(row[field]) for field in ("ij_max", "ij_min", "ij_max"))
    if not (
        0 <= k < len(depth_edges) - 1
        and int(row["k_min"]) <= k <= int(row["k_max"])
        and 0 <= i < nx - 1
        and 0 <= j_min <= j_max < len(widths_y)
    ):
        raise ValueError("casing hole does not resolve to a sealed casing face with an adjacent cell")
    overlapping = casings.loc[
        (casings["name"] != hole.casing)
        & (casings["ij_max"] == i)
        & (casings["ij_min"] <= j_max)
        & (casings["ij_max"] >= j_min)
        & (casings["k_min"] <= k)
        & (casings["k_max"] >= k)
    ]
    if not overlapping.empty:
        raise ValueError("casing hole interface is shared with another casing at this grid resolution")

    dz = float(depth_edges[k + 1] - depth_edges[k])
    face_areas = widths_y[j_min : j_max + 1] * dz
    if not np.isfinite(face_areas).all() or not (face_areas > 0).all():
        raise ValueError("casing hole face areas must be finite and positive")
    radius = hole.diameter_m / 2
    area = pi * radius * radius
    available = fsum(float(value) for value in face_areas)
    if not isfinite(area) or area <= 0 or (area > available and not isclose(area, available, rel_tol=1e-12)):
        raise ValueError("casing hole area exceeds the available +X casing side area in this layer")

    edges_y = np.concatenate(([0.0], np.cumsum(widths_y)))
    midpoint = (edges_y[j_min] + edges_y[j_max + 1]) / 2
    order = sorted(
        range(j_min, j_max + 1),
        key=lambda j: (round(abs((edges_y[j] + edges_y[j + 1]) / 2 - midpoint), 12), j),
    )
    faces = []
    remaining = area
    for j in order:
        if remaining <= 0:
            break
        face_area = float(widths_y[j] * dz)
        allocated = min(remaining, face_area)
        faces.append(HoleFace(i + 1, j + 1, k + 1, face_area, allocated, allocated / face_area))
        remaining -= allocated
    if not isclose(fsum(face.opening_area_m2 for face in faces), area, rel_tol=1e-12, abs_tol=0):
        raise ValueError("casing hole allocation failed to conserve opening area")
    return tuple(faces)


def write_casing_hole(faces: tuple[HoleFace, ...], stream: TextIO) -> None:
    if not faces:
        return
    stream.write("-- SCREEN experimental casing hole: fixed +X side\nEQUALS\n")
    for face in faces:
        stream.write(
            f"MULTX {face.multiplier:.17g} {face.i} {face.i} {face.j} {face.j} {face.k} {face.k} /\n"
        )
    stream.write("/\n")
