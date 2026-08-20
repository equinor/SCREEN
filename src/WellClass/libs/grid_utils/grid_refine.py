from typing import List, Tuple

import numpy as np
import pandas as pd

from .extract_grid_utils import (
    extract_xz_corn_coords,
    extract_xz_prop_slice,
)
from .grid_coarse import GridCoarse
from .grid_refine_base import GridRefineBase


class GridRefine(GridRefineBase):
    def __init__(self, grid_coarse: GridCoarse, LGR_sizes_x: List[float], LGR_sizes_y: List[float], LGR_sizes_z: np.ndarray, min_grd_size: float):
        """class for LGR mesh for the center coarse cell

        Args:

            grid_coarse (GridCoarse): information on coarse grid
            LGR_sizes_x (list[float]): LGR x grid intervals
            LGR_sizes_y (list[float]): LGR y grid intervals
            LGR_sizes_z (np.ndarray): LGR DZ inernals
            min_grd_size (float): minimize grid size
        """

        super().__init__(grid_coarse, LGR_sizes_x, LGR_sizes_y, LGR_sizes_z, min_grd_size)

    # TODO(hzh): Here the input will be modified.
    # This is not a good practice of programming!!!
    # Will come back to this.
    def build_LGR(self, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barrier_regions_df: pd.DataFrame) -> None:
        """assign material types to corresponding permeabilities.

        Args:

            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions

        Returns:
            an updated dataframe specifically for GaP code
        """

        # 1. compute lateral number of refined grid
        self._compute_num_lateral_fine_grd(holes_df, casings_df, barrier_regions_df)

        # 2. set bounding box
        self._compute_bbox(holes_df, casings_df, barrier_regions_df)

        # 3. set material type
        self._set_material_type(holes_df, casings_df, barrier_regions_df)

        # 4. set permeability
        self._set_permeability(holes_df, casings_df, barrier_regions_df)

        # 0. for GaP code
        gap_casing_df = self._compute_bbox_gap_casing(casings_df)

        return gap_casing_df

    def extract_xz_corn_coords(self) -> Tuple[np.ndarray, np.ndarray]:
        """generate xcorn and zcorn coordinates"""

        # for convenience
        mesh_df = self.mesh_df

        # for shifting
        sDX = self.main_grd_dx / 2
        sDY = self.main_grd_dy / 2

        # generate grid coordinates for plotting
        xcorn, zcorn = extract_xz_corn_coords(mesh_df, sDX, sDY)

        return xcorn, zcorn

    def extract_xz_slice(self, prop="PERMX") -> np.ndarray:
        """generate x-z PERM slice

        Args:
            prop (str): the property name, default: PERMX

        Returns:
            np.ndarray: x-z slice of the property
        """
        # for convenience
        mesh_df = self.mesh_df

        # extract permeability
        Z = extract_xz_prop_slice(mesh_df, prop=prop)

        return Z
