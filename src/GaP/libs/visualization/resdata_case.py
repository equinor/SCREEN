"""Read combined EGRID/INIT data for visualization adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from resdata.grid import Grid
from resdata.resfile import ResdataInitFile, ResdataRestartFile


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