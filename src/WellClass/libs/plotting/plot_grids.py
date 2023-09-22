
from typing import Union

from ..grid_utils.grid_coarse import GridCoarse
from ..grid_utils.grid_refine import GridRefine
from ..grid_utils.grid_lgr import GridLGR

from .plot_utils import plot_well_perm

def plot_grid(my_well, 
              grid: Union[GridCoarse, GridRefine, GridLGR], 
              *, 
              on_coarse=None):
    """ Plot well sketch and 2D slice of the permeability
    """
    
    # auto detected if on_coarse is not selected by user
    if on_coarse is None:
        on_coarse = False
        if type(grid) == GridCoarse:
            on_coarse = True

    # x-z corner coordinates at center y
    xcorn, zcorn = grid.extract_xz_corn_coords()

    # extract z PERM values at center y coarse grid
    Z = grid.extract_xz_slice()

    # plot x-z slice
    plot_well_perm(my_well, x=xcorn, y=zcorn, Z=Z, on_coarse=on_coarse)
