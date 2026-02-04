import pathlib
from typing import Tuple, Union

import numpy as np

# from ecl.eclfile import EclFile, EclRestartFile
from resdata.grid import Grid
from resdata.resfile import ResdataInitFile

from .extract_grid_utils import (
    extract_xz_corn_coords,
    extract_xz_prop_slice,
)


class GridLGR:
    def __init__(self, sim_case: Union[str, pathlib.Path]) -> None:
        """This is used to process .EGRID file

        Args:
            sim_case (str): name prefix for eclipse/pflotran case
        """

        # convert it to string, in case it is pathlib.Path
        sim_case = str(sim_case)

        # Get grid dimensions and coordinates
        grid = Grid(sim_case + ".EGRID")
        # init = EclGrid(simcase + ".INIT")
        init = ResdataInitFile(grid, sim_case + ".INIT")

        # the coarse grid dimensions
        self.NX, self.NY, self.NZ, _ = grid.get_dims()

        # Process init file
        lgr_name = grid.get_lgr(0).get_name()
        lgr_grid = grid.get_lgr(lgr_name)

        # # Store INIT parameters into a Pandas Dataframe

        lgr_index = lgr_grid.export_index()

        # Static properties Dataframe
        for key in init.keys():
            try:
                lgr_index[key] = init[key][1].numpy_view()
            except Exception:
                continue

        #
        self.lgr_index = lgr_index

        # compute middle index for extraction of DX and DY
        mid_i = lgr_index.i.max() // 2  # noqa: F841
        mid_j = lgr_index.j.max() // 2  # noqa: F841

        # compute DX and DY on the coarse grid by summing LGR grid
        self.main_grd_dx = lgr_index.query("j==@mid_j&k==0").DX.sum()
        self.main_grd_dy = lgr_index.query("i==@mid_i&k==0").DY.sum()

    def extract_xz_corn_coords(self) -> Tuple[np.ndarray, np.ndarray]:
        """generate xcorn and zcorn coordinates"""

        # for convenience
        lgr_index = self.lgr_index

        # shifting half coarse grid
        sDX = self.main_grd_dx / 2
        sDY = self.main_grd_dy / 2

        # generate corner grid coordinates for plotting
        xcorn, zcorn = extract_xz_corn_coords(lgr_index, sDX, sDY)

        return xcorn, zcorn

    def extract_xz_slice(self, prop="PERMX") -> np.ndarray:
        """generate x-z PERM slice

        Args:
            prop (str): the property name, default: PERMX

        Returns:
            np.ndarray: x-z slice of the property
        """
        # for convenience
        lgr_index = self.lgr_index

        # extract permeability
        Z = extract_xz_prop_slice(lgr_index, prop=prop)

        return Z
