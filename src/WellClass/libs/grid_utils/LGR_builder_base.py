import os

import pandas as pd

from src.GaP.libs.carfin.CARFIN_core import CARFIN_keywords, endCARFIN2, pre_CARFIN

from .LGR2GaP import df_to_gap_barrier, df_to_gap_casing
from .LGR_bbox import compute_bbox_for_reopen


class LGRBuilderBase:
    def _build_grdecl(
        self,
        output_folder: str,
        LGR_NAME: str,
        holes_df: pd.DataFrame,
        casings_df: pd.DataFrame,
        barriers_mod_df: pd.DataFrame,
        NX: int,
        NY: int,
        main_grd_i: int,
        main_grd_j: int,
        main_grd_min_k: int,
        main_grd_max_k: int,
        no_of_layers_in_OB: int,
        LGR_sizes_x,
        LGR_numb_z,
        min_grd_size: float,
    ):
        """build grdecl file and output it"""
        # 0. prepare file for output

        # check output directory
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)

        # generate output file name
        out_fname = os.path.join(output_folder, LGR_NAME + ".grdecl")

        # open it
        if os.path.exists(out_fname):
            O = open(out_fname, "r+")  # noqa: E741
        else:
            O = open(out_fname, "x")  # noqa: E741

        O.truncate(0)

        # 1. start the process
        pre_CARFIN(LGR_NAME, NX, NY, main_grd_i + 1, main_grd_j + 1, no_of_layers_in_OB, O)

        # 2. keywods
        CARFIN_keywords(LGR_NAME, main_grd_i + 1, main_grd_j + 1, main_grd_min_k + 1, main_grd_max_k + 1, LGR_sizes_x, LGR_numb_z, min_grd_size, O)

        # 3. the pipes/openholes/barriers
        df_to_gap_casing(holes_df, casings_df, LGR_NAME, O)

        df_to_gap_barrier(barriers_mod_df, LGR_NAME, O)

        # 4. handle reopen hole
        nz_ovb = 10 * no_of_layers_in_OB  # total number of ovb layers (refined grid)

        # bbox
        reopen_ID, x_min_reopen, x_max_reopen = compute_bbox_for_reopen(holes_df, casings_df, nz_ovb)

        endCARFIN2(
            LGR_NAME,
            reopen_ID,
            x_min_reopen + 1,  # fortran indexing
            x_max_reopen + 1,  # fortran indexing
            nz_ovb,
            LGR_sizes_x,
            O,
        )

        # 2. done
        O.close()

        # for qc
        print("Output LGR CARFIN to: ", os.path.abspath(out_fname))
