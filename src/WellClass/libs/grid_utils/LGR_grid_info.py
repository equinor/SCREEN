
from typing import Tuple

import numpy as np
import pandas as pd

from .grid_coarse import GridCoarse

from .LGR_grid_utils import (
    compute_ngrd,
    generate_LGR_xy,
    generate_LGR_z,
)

class LGRGridInfo:

    def __init__(self,
                 grid_coarse: GridCoarse, 
                 annulus_df: pd.DataFrame,
                 holes_df: pd.DataFrame,
                 Ali_way: bool):
        """ LGR grid information in x, y, z directions. We are going to compute the grid sizes in lateral (x and y) and vertical directions

            Args:
                grid_coarse (GridCoarse): all information about coarse grid
                annulus_df (pd.DataFrame): information about annulus
                holes_df (pd.DataFrame): drilled-hole intervals
                Ali_way (bool): use Ali's algorithm to compute lateral grids and apply refdepth in z direction
        """

        # initialize coarse grid parameters
        self.NX, self.NY = grid_coarse.NX, grid_coarse.NY
        self.main_grd_dx, self.main_grd_dy = grid_coarse.main_grd_dx, grid_coarse.main_grd_dy
        self.main_grd_i, self.main_grd_j = grid_coarse.main_grd_i, grid_coarse.main_grd_j
        self.main_grd_min_k, self.main_grd_max_k = grid_coarse.main_grd_min_k, grid_coarse.main_grd_max_k

        # DZs for reservoir and overburden, only on center cell of coarse grid
        self.DZ_rsrv = grid_coarse.DZ_rsrv
        self.DZ_ovb_coarse = grid_coarse.DZ_ovb_coarse

        # number of layers of ovb
        self.no_of_layers_in_OB = grid_coarse.no_of_layers_in_OB

        # reference depth wheer LGR starts
        self.ref_depth = 0
        if Ali_way: 
            self.ref_depth = grid_coarse.ref_depth

        ######################################

        # ### 1. Compute minimum grid size
        self.min_grd_size = self._compute_min_grd_size(annulus_df, Ali_way)

        # #### 2. Compute number of cells of horizontal LGR
        self.num_lateral_fine_grd = self._compute_num_lateral_fine_grd(holes_df)

        # #### 3. compute LGR sizes

        # 3.1 compute LGR sizes in x-y directions
        self.LGR_sizes_x, self.LGR_sizes_y = self._compute_LGR_sizes_xy(Ali_way)

        # 3.2 comptue LGR sizes in z direction
        self.LGR_sizes_z, self.LGR_numb_z, self.LGR_depths = self._compute_LGR_sizes_z()

    def _compute_min_grd_size(self, 
                              annulus_df: pd.DataFrame, 
                              Ali_way: bool) -> float:
        """ Compute minimum grid size

            Args:

                annulus_df (pd.DataFrame): information about annulus
                Ali_way (bool): use Ali's algorithm to compute lateral grids and apply refdepth in z direction

            Returns:
                float: minimum grid size
        """

        # 0. minimum grid size

        # minimum grid size depends on minimum annulus thickness
        min_grd_size = annulus_df['thick_m'].min()

        if min_grd_size < 0.05:
            min_grd_size = 0.05

        print(f'Minimimum grid size is {min_grd_size*100:.2f} cm')

        # TODO(hzh): manually set it
        if Ali_way:
            min_grd_size = 0.05

        return min_grd_size
    
    def _compute_num_lateral_fine_grd(self, 
                                      holes_df: pd.DataFrame) -> float:
        """ compute number of LGR lateral grids

            Args:

                holes_df (pd.DataFrame): drilled-hole intervals

            Returns:
                float: number of LGR lateral grids
        """

        # only for convenience
        min_grd_size = self.min_grd_size

        # 
        drilling_series = holes_df['diameter_m'].map(lambda x: compute_ngrd(x, min_grd_size))

        return drilling_series.max()
    
    def _compute_LGR_sizes_xy(self, 
                              Ali_way: bool) -> Tuple:
        """ Compute LGR grid sizes in x-y directions

            Args:

                Ali_way (bool): use Ali's algorithm to compute lateral grids and apply refdepth in z direction

            Returns:

                Tuple: LGR_sizes_x, LGR_sizes_y
        """

        # for convenience
        num_lateral_fine_grd = self.num_lateral_fine_grd
        min_grd_size = self.min_grd_size
        main_grd_dx = self.main_grd_dx
        main_grd_dy = self.main_grd_dy

        # 3.1 generate the LGR grid sizes in x-y
        LGR_sizes_x, LGR_sizes_y, _ = generate_LGR_xy(num_lateral_fine_grd, 
                                                        min_grd_size, 
                                                        main_grd_dx, main_grd_dy,
                                                        Ali_way=Ali_way)

        return LGR_sizes_x, LGR_sizes_y
    
    def _compute_LGR_sizes_z(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """ Compute LGR grid sizes in z direction

            Returns:

                Tuple: LGR_sizes_z, LGR_numb_z, LGR_depths
        """
        # for convenience
        DZ_rsrv = self.DZ_rsrv
        DZ_ovb_coarse = self.DZ_ovb_coarse 
        ref_depth = self.ref_depth

        # 3.2 generate the LGR grid sizes in x-y

        # TODO(hzh): to make LGR starts at ref_depth
        LGR_sizes_z, LGR_numb_z, LGR_depths, _ = generate_LGR_z(DZ_rsrv, DZ_ovb_coarse, ref_depth)

        return LGR_sizes_z, LGR_numb_z, LGR_depths

