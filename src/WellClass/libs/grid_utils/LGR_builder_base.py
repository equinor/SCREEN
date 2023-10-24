
import os
import pandas as pd

from src.GaP.libs.carfin.CARFIN_core import (
    pre_CARFIN,
    CARFIN_keywords,
    endCARFIN
)

from .LGR2GaP import (
    df_to_gap_casing,
    df_to_gap_barrier
)

class LGRBuilderBase:

    def _build_grdecl(self, 
                      output_folder: str, 
                      LGR_NAME: str,
                      drilling_df: pd.DataFrame, 
                      casings_df: pd.DataFrame, 
                      barriers_mod_df: pd.DataFrame,
                      NX: int, NY: int,
                      main_grd_i: int, main_grd_j: int,
                      main_grd_min_k: int, main_grd_max_k: int,
                      no_of_layers_in_OB: int,
                      LGR_sizes_x,
                      LGR_numb_z,
                      min_grd_size: float):
        """ build grdecl file and output it
        """
        # 0. prepare file for output

        # check output directory
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)

        # generate output file name
        out_fname = os.path.join(output_folder, LGR_NAME+'.grdecl')

        # open it
        if os.path.exists(out_fname):
            O = open(out_fname,"r+")  # noqa: E741
        else: 
            O = open(out_fname,"x")  # noqa: E741

        O.truncate(0)

        # 1. start the process
        pre_CARFIN(LGR_NAME,
                    NX, NY,
                    main_grd_i+1, main_grd_j+1, 
                    no_of_layers_in_OB, 
                    O)
        
        # 2. keywods
        CARFIN_keywords(LGR_NAME,
                        main_grd_i+1, main_grd_j+1, 
                        main_grd_min_k+1, main_grd_max_k+1, 
                        LGR_sizes_x, 
                        LGR_numb_z, 
                        min_grd_size,
                        O)

        # 3. the pipes/openholes/barriers
        df_to_gap_casing(drilling_df, 
                         casings_df,
                         LGR_NAME,
                         O)
        
        df_to_gap_barrier(barriers_mod_df,
                          LGR_NAME,
                          O)
        
        # determine where ovb is
        
        # find minimum IDs for casings
        reopen_ID = casings_df.diameter_m.min()

        # 4. open hole
        endCARFIN(LGR_NAME,
                    reopen_ID,
                    LGR_sizes_x, 
                    main_grd_min_k+1, 
                    min_grd_size,
                    no_of_layers_in_OB,
                    O)

        # 2. done
        O.close()

        # for qc
        print ('Output LGR CARFIN to: ', os.path.abspath(out_fname))

