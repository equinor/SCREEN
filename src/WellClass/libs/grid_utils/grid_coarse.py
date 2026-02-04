
# handle type hints problem for python version < 3.10
from typing import Union, Tuple

import numpy as np
import pandas as pd

from resdata.grid import Grid
from resdata.resfile import ResdataInitFile

# from ecl.eclfile import EclFile, EclRestartFile
#import rips 

from .extract_grid_utils import (
    extract_xz_corn_coords,
    extract_xz_prop_slice,
)

class GridCoarse:

    def __init__(self, simcase: str):
        """ Loading the model
             
             - Load the PFT grid, init and restart files

             - Grid contains geometry specs

             - INIT contains static properties (i.e. poro., perm., transmissibilities)
             
             - RST contains dynamic properties (i.e. saturations, pressure)

            Args:
                simcase (str): name prefix for ECL grid
        """

        #Get grid dimensions and coordinates
        grid = Grid(simcase + ".EGRID") 
        #init = EclGrid(simcase + ".INIT") 
        init = ResdataInitFile(grid, simcase + ".INIT")
        # restart file
        # rst = EclRestartFile(grid, simcase + ".UNRST")

        # ## The grid dimensions
        self.NX, self.NY, self.NZ, _ = grid.get_dims()

        print(f'Coarse grid dimension: nx={self.NX}, ny={self.NY}, nz={self.NZ}')

        # # Store INIT parameters into a Pandas Dataframe: grid_init

        self.grid_init = grid.export_index()

        # Static properties Dataframe
        for key in init.keys():
                try:
                        self.grid_init[key] = init[key][0].numpy_view()
                except Exception:
                        continue

        # set up other grid-related information
        self._set_grid_info(self.grid_init)
        
        # set up cell coordinates
        self._set_cell_coords(self.grid_init)

    def _set_cell_coords(self, grid_init: pd.DataFrame):
        """ Create cell coordinate X, Y, Z

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
        """

        # generate cell coordinates by shifting half cell size
        xcoord = (grid_init.query("j==0&k==0").DX.cumsum() - grid_init.query("j==0&k==0").DX/2).values
        ycoord = (grid_init.query("i==0&k==0").DY.cumsum() - grid_init.query("i==0&k==0").DY/2).values
        zcoord = (grid_init.query("i==0&j==0").DZ.cumsum() - grid_init.query("i==0&j==0").DZ/2).values

        # TODO(hzh): a bug?
        # map_X = dict(zip(grid_init.query("j==0&j==0")['i'], xcoord))
        map_X = dict(zip(grid_init.query("j==0&k==0")['i'], xcoord))
        map_Y = dict(zip(grid_init.query("i==0&k==0")['j'], ycoord))
        map_Z = dict(zip(grid_init.query("i==0&j==0")['k'], zcoord))

        # save cell coordinates to DataFrame
        grid_init['X'] = grid_init['i'].map(map_X)
        grid_init['Y'] = grid_init['j'].map(map_Y)
        grid_init['Z'] = grid_init['k'].map(map_Z)

        # mid values
        mid_i = self.main_grd_i
        mid_j = self.main_grd_j

        self.xcoord0 = xcoord[mid_i]
        self.ycoord0 = ycoord[mid_j]

    def _set_grid_info(self, grid_init: pd.DataFrame):
        """ Grid information for coarse grid

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
        """
        
        # Retrieve coarse x-y grid indexes where LGR will be placed
        # i.e., center grid
        self.main_grd_i = grid_init.i.max()//2
        self.main_grd_j = grid_init.j.max()//2

        # Rettrieve min and max k-index for column where LGR will be placed
        self.main_grd_min_k = grid_init.k.min()
        self.main_grd_max_k = grid_init.k.max()

        # Retrieve coarse cell sizes
        self._set_main_grd_dx_dy(grid_init, self.main_grd_i, self.main_grd_j)

        # Retrieve refdepth where LGR starts
        self._set_ref_depth(grid_init, self.main_grd_i, self.main_grd_j)

        # Retrieve number of cells representing water column and overburden
        self._set_no_layers(grid_init, self.main_grd_i, self.main_grd_j)

        self._set_DZ_rsrv_ovb(grid_init, self.main_grd_i, self.main_grd_j)

    def _set_main_grd_dx_dy(self, 
                            grid_init: pd.DataFrame, 
                            main_grd_i: int, 
                            main_grd_j: int):
        """ coarse cell size at the center grid

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
                main_grd_i (int): index of center x grid
                main_grd_j (int): index of center y grid
        """

        self.main_grd_dx = grid_init.query('i == @main_grd_i & j == @main_grd_j & k == k.min()')['DX'].iloc[0]
        self.main_grd_dy = grid_init.query('i == @main_grd_i & j == @main_grd_j & k == k.min()')['DY'].iloc[0]
    
    def _set_ref_depth(self, 
                        grid_init: pd.DataFrame, 
                        main_grd_i: int, 
                        main_grd_j: int):
        """ set reference depth for LGR grid

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
                main_grd_i (int): index of center x grid
                main_grd_j (int): index of center y grid
        """
    
        # Retrieve all DZ in coarse grid, not used
        main_DZ    = grid_init.query('i == @main_grd_i & j == @main_grd_j')['DZ'].values

        main_DEPTH = grid_init.query('i == @main_grd_i & j == @main_grd_j')['DEPTH'].values

        # depth where LGR starts
        self.ref_depth = main_DEPTH[0] - 0.5*main_DZ[0]

    def _set_no_layers(self, 
                        grid_init: pd.DataFrame, 
                        main_grd_i: int, 
                        main_grd_j: int):
        """ Retrieve number of cells representing water column and overburden

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
                main_grd_i (int): index of center x grid
                main_grd_j (int): index of center y grid
        """

        self.no_of_layers_in_OB    = grid_init.query('i==@main_grd_i & j == @main_grd_j & DZ >  10')['DZ'].shape[0]
        self.no_of_layers_below_OB = grid_init.query('i==@main_grd_i & j == @main_grd_j & DZ <= 10')['DZ'].shape[0]
    
    def _set_DZ_rsrv_ovb(self, 
                         grid_init: pd.DataFrame, 
                         main_grd_i: int, 
                         main_grd_j: int, 
                         dz0: Union[float, int] =10):
        """ DZs for rsrv and ovb

            Args:
                grid_init (pd.DataFrame): dataframe containing coarse grid information
                main_grd_i (int): index of center x grid
                main_grd_j (int): index of center y grid
                dz0 (float): the dz value to distinguish zones between reservoir and ovb
        """

        # 3.1 DZs for reservoir
        self.DZ_rsrv = grid_init.query('i==@main_grd_i & j == @main_grd_j & DZ <= @dz0')['DZ'].values

        # 3.2 DZs for coarse grid
        self.DZ_ovb_coarse = grid_init.query('i==@main_grd_i & j == @main_grd_j & DZ > @dz0')['DZ'].values
    
    
    def extract_xz_corn_coords(self) -> Tuple[np.ndarray, np.ndarray]:
        """ generate xcorn and zcorn coordinates
        """

        # for convenience
        grid_init = self.grid_init

        # shift grid coordinates half-length in x-y directions, i.e., [0, 3900] => [-1900, 2100]
        # but not in z direction
        sDX = self.xcoord0
        sDY = self.ycoord0

        # generate grid coordinates for plotting
        xcorn, zcorn = extract_xz_corn_coords(grid_init, sDX, sDY)

        return xcorn, zcorn 
 
    def extract_xz_slice(self, prop='PERMX') -> np.ndarray:
        """ generate x-z PERM slice
        
            Args:
                prop (str): the property name, default: PERMX

            Returns:
                np.ndarray: x-z slice of the property
        """
        # for convenience
        grid_init = self.grid_init

        # extract permeability
        Z = extract_xz_prop_slice(grid_init, prop=prop)

        return Z
