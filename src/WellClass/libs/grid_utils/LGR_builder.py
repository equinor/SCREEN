import pandas as pd

# coarse and refined grid
from .grid_coarse import GridCoarse
from .grid_refine import GridRefine
from .LGR_builder_base import LGRBuilderBase

# utilities for LGR grid
from .LGR_grid_info import LGRGridInfo


class LGRBuilder(LGRBuilderBase):
    def __init__(self, simcase: str, annulus_df: pd.DataFrame, holes_df: pd.DataFrame, Ali_way: bool):
        """Builder for generating LGR grid

        Args:
            simcase (str): simulation case, information about coarse grid
            annulus_df (pd.DataFrame): information about annulus
            holes_df (pd.DataFrame): drilled-hole intervals
            Ali_way (bool): use Ali's algorithm to compute lateral grids and apply refdepth in z direction
        """

        ##### 1. grid_coarse
        # Loading the model
        self.grid_coarse = GridCoarse(str(simcase))

        ##### 2. LGR grid sizes
        # LGR grid information in x, y, z directions
        self.lgr_info = LGRGridInfo(self.grid_coarse, annulus_df, holes_df, Ali_way)

        ##### 3. LGR refined grid
        # Set up dataframe for LGR mesh
        self.grid_refine = GridRefine(
            self.grid_coarse, self.lgr_info.LGR_sizes_x, self.lgr_info.LGR_sizes_y, self.lgr_info.LGR_sizes_z, self.lgr_info.min_grd_size
        )

    def build_grdecl(
        self, output_folder: str, LGR_NAME: str, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barriers_mod_df: pd.DataFrame
    ) -> pd.DataFrame:
        """build .grdecl file and output it

        Args:

            output_folder (str): output folder
            LGR_NAME (str): output file name
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barriers_mod_df (pd.DataFrame): information about barrier
        """

        ##### 4. build LGR
        gap_casing_df = self.grid_refine.build_LGR(holes_df, casings_df, barriers_mod_df)

        ##### 5. output LGR
        self._build_grdecl(
            output_folder,
            LGR_NAME,
            holes_df,
            gap_casing_df,  # casings_df,
            barriers_mod_df,
            self.grid_coarse.NX,
            self.grid_coarse.NY,
            self.grid_coarse.main_grd_i,
            self.grid_coarse.main_grd_j,
            self.grid_coarse.main_grd_min_k,
            self.grid_coarse.main_grd_max_k,
            self.grid_coarse.no_of_layers_in_OB,
            self.lgr_info.LGR_sizes_x,
            self.lgr_info.LGR_numb_z,
            self.lgr_info.min_grd_size,
        )

        return gap_casing_df
