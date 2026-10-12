import numpy as np
import pandas as pd
from resdata.grid import Grid

from src.GaP.libs.grid_utils.casing_hole import refined_depth_edges, resolve_casing_hole, validate_layer_thicknesses
from src.GaP.libs.models.casing_hole import CasingHole

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
        self.simcase = simcase
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
        self,
        output_folder: str,
        LGR_NAME: str,
        holes_df: pd.DataFrame,
        casings_df: pd.DataFrame,
        barrier_regions_df: pd.DataFrame,
        *,
        casing_hole: CasingHole | None = None,
    ) -> pd.DataFrame:
        """build .grdecl file and output it

        Args:

            output_folder (str): output folder
            LGR_NAME (str): output file name
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions
        """

        ##### 4. build LGR
        gap_casing_df = self.grid_refine.build_LGR(holes_df, casings_df, barrier_regions_df)
        self.casing_hole_faces = ()
        if casing_hole is not None:
            grid = Grid(self.simcase + ".EGRID")
            depth_edges = refined_depth_edges(
                grid,
                self.grid_coarse.main_grd_i,
                self.grid_coarse.main_grd_j,
                self.lgr_info.LGR_numb_z,
                self.grid_coarse.main_grd_min_k,
            )
            validate_layer_thicknesses(depth_edges, self.lgr_info.LGR_numb_z, self.lgr_info.LGR_sizes_z)
            # CARFIN HYFIN uses rounded relative widths, normalized to the parent cell.
            ratios_y = np.round(np.asarray(self.lgr_info.LGR_sizes_x) / self.lgr_info.min_grd_size, 2)
            parent_cell = (self.grid_coarse.main_grd_i, self.grid_coarse.main_grd_j, self.grid_coarse.main_grd_min_k)
            parent_dy = grid.get_cell_corner(2, ijk=parent_cell)[1] - grid.get_cell_corner(0, ijk=parent_cell)[1]
            widths_y = ratios_y / ratios_y.sum() * parent_dy
            self.casing_hole_faces = resolve_casing_hole(
                casing_hole, gap_casing_df, depth_edges, widths_y, self.grid_refine.nx
            )

        ##### 5. output LGR
        self._build_grdecl(
            output_folder,
            LGR_NAME,
            holes_df,
            gap_casing_df,  # casings_df,
            barrier_regions_df,
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
            self.casing_hole_faces,
        )

        return gap_casing_df
