"""Read combined EGRID/INIT data for visualization adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from resdata.grid import Grid
from resdata.resfile import ResdataInitFile, ResdataRestartFile


def hexahedron_polygons(cell_count: int) -> list[int]:
    """Encode six quad faces per hexahedral cell for Webviz Grid3DLayer."""
    faces = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    polygons: list[int] = []
    for cell_index in range(cell_count):
        for face in faces:
            polygons.extend([4, *(cell_index * 8 + corner for corner in face)])
    return polygons


class ResdataCase:
    """Expose grid geometry and static properties from one simulator case."""

    def __init__(self, case_prefix: str | Path):
        prefix = Path(case_prefix)
        self.prefix = prefix
        self.grid = Grid(str(prefix.with_suffix(".EGRID")))
        self.init = ResdataInitFile(self.grid, str(prefix.with_suffix(".INIT")))
        restart_path = prefix.with_suffix(".UNRST")
        self.restart = ResdataRestartFile(self.grid, str(restart_path)) if restart_path.exists() else None
        self.index = self.grid.export_index()

    @property
    def dimensions(self) -> tuple[int, int, int, int]:
        """Return NX, NY, NZ, and global cell count."""
        return self.grid.get_dims()

    @property
    def keywords(self) -> list[str]:
        """Return available static INIT keywords."""
        return list(self.init.keys())

    def init_vector(self, keyword: str, record: int = 0) -> np.ndarray:
        """Return one INIT keyword as a numeric flat array."""
        return np.asarray(self.init[keyword][record].numpy_view())

    def init_array(self, keyword: str, record: int = 0, fill_value: float = np.nan) -> np.ndarray:
        """Return an INIT keyword reshaped to simulator IJK order."""
        vector = self.init_vector(keyword, record)
        values = np.full(vector.shape, fill_value, dtype=float)
        values[: vector.size] = vector
        return values.reshape(self.dimensions[:3], order="F")

    @property
    def restart_keywords(self) -> list[str]:
        """Return available dynamic keywords, or an empty list without UNRST."""
        return list(self.restart.keys()) if self.restart is not None else []

    def restart_array(self, keyword: str, record: int = 0) -> np.ndarray:
        """Return one UNRST keyword reshaped to simulator IJK order."""
        if self.restart is None:
            raise FileNotFoundError(f"restart file not found for {self.prefix}")
        vector = np.asarray(self.restart[keyword][record].numpy_view())
        return vector.reshape(self.dimensions[:3], order="F")

    def cell_centers(self, active_indices: np.ndarray | None = None) -> np.ndarray:
        """Return cell centers as an ``(N, 3)`` XYZ array."""
        if active_indices is None:
            active_indices = self.index["active"].to_numpy()
        return np.asarray([self.grid.get_xyz(active_index=int(index)) for index in active_indices], dtype=float)

    def cell_corners(self) -> np.ndarray:
        """Return all cell corner coordinates from the combined EGRID."""
        return np.asarray(self.grid.export_corners(self.index))

    def lgr_parent_indices(self) -> np.ndarray:
        """Return combined-grid active indices that own an embedded LGR."""
        parent_indices = []
        for index in self.index["active"]:
            try:
                if self.grid.get_cell_lgr(active_index=int(index)) is not None:
                    parent_indices.append(int(index))
            except IndexError:
                continue
        return np.asarray(parent_indices, dtype=int)

    def embedded_lgr(self):
        """Return the embedded LGR object, or ``None`` when no LGR exists."""
        parent_indices = self.lgr_parent_indices()
        if len(parent_indices) == 0:
            return None
        return self.grid.get_cell_lgr(active_index=int(parent_indices[0]))

    def lgr_slice_indices(self, j: int | None = None) -> np.ndarray:
        """Return embedded-LGR cell indices for one J column."""
        lgr = self.embedded_lgr()
        if lgr is None:
            return np.asarray([], dtype=int)
        lgr_index = lgr.export_index()
        selected_j = lgr.get_dims()[1] // 2 if j is None else j
        if not 0 <= selected_j < lgr.get_dims()[1]:
            raise ValueError(f"J column {selected_j} is outside 0..{lgr.get_dims()[1] - 1}")
        return lgr_index.loc[lgr_index["j"] == selected_j, "active"].to_numpy(dtype=int)

    def lgr_xz_slice(self, j: int | None = None) -> dict[str, np.ndarray]:
        """Return geometry for a south-facing XZ slice through the embedded LGR."""
        lgr = self.embedded_lgr()
        if lgr is None:
            return {"indices": np.asarray([], dtype=int), "centers": np.empty((0, 3)), "corners": np.empty((0, 8, 3))}
        indices = self.lgr_slice_indices(j)
        centers = np.asarray([lgr.get_xyz(active_index=int(index)) for index in indices], dtype=float)
        corners = np.asarray(lgr.export_corners(lgr.export_index().loc[lgr.export_index()["active"].isin(indices)]), dtype=float)
        return {"indices": indices, "centers": centers, "corners": corners.reshape((-1, 8, 3))}

    def lgr_property_slice(self, source: str, keyword: str, record: int = 0, j: int | None = None) -> dict[str, np.ndarray]:
        """Return LGR slice geometry and parent-cell property values."""
        slice_data = self.lgr_xz_slice(j)
        if not len(slice_data["indices"]):
            return {**slice_data, "properties": np.asarray([], dtype=float)}

        values = self.init_array(keyword, record) if source == "INIT" else self.restart_array(keyword, record)
        parent_centers = self.cell_centers(self.lgr_parent_indices())
        parent_values = values.reshape(-1, order="F")[self.lgr_parent_indices()]
        lgr_z = slice_data["centers"][:, 2]
        parent_z = parent_centers[:, 2]
        nearest_parent = np.abs(lgr_z[:, None] - parent_z[None, :]).argmin(axis=1)
        return {**slice_data, "properties": parent_values[nearest_parent].astype(float)}

    @staticmethod
    def south_xz_view(vertical_scale: float = 0.005) -> dict[str, object]:
        """Return the predefined orthographic south-facing XZ view settings."""
        return {
            "projection": "orthographic",
            "view_direction": "south",
            "plane": "xz",
            "show_coarse_grid": False,
            "vertical_scale": vertical_scale,
        }

    def south_xz_camera(self, vertical_scale: float = 0.001) -> dict[str, object]:
        """Return a 2D XZ camera fit to the full LGR height."""
        slice_data = self.lgr_xz_slice()
        if not len(slice_data["corners"]):
            raise ValueError("South XZ camera requires an embedded LGR")
        corners = slice_data["corners"]
        minimum = corners.reshape(-1, 3).min(axis=0)
        maximum = corners.reshape(-1, 3).max(axis=0)
        center = (minimum + maximum) / 2.0
        height = max((maximum[2] - minimum[2]) * vertical_scale, 1e-6)
        half_width = height * 0.002
        return {
            "target": [float(center[0]), float(center[2] * vertical_scale)],
            "zoom": [
                float(center[0] - half_width),
                float(minimum[2] * vertical_scale),
                0.0,
                float(center[0] + half_width),
                float(maximum[2] * vertical_scale),
                0.0,
            ],
        }
