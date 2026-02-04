""" initialize 3D Eclipse grid
"""
import numpy as np

from resdata.grid import Grid
from resdata.resfile import ResdataInitFile


def make_stat_3d_main(grid: Grid, 
                      init: ResdataInitFile, 
                      vec: str, 
                      default_val=-1)->np.ndarray:
    """ making the 3D grid

        Args:
            grid (Grid): Eclipse grid information  
            init (ResdataInitFile): Eclipse init grid information
            vec (str): property name
            default_val (float): default is -1

        Returns:
            np.ndarray: the 3D grid
    """

    ix = grid.export_index()

    aix = np.where(ix.active>=0)
    aix = np.where(init['PORV'][0].numpy_view()>0.0)

    # get 3D dimensions
    nx,ny,nz = grid.get_dims()[:3]
    n= nx*ny*nz

    # allocate 3D spaces with default value
    vec1d = default_val*np.ones(shape=(n,))

    vec1d[aix] = init[vec]

    vec3d = vec1d.reshape((nx,ny,nz), order='F')

    return vec3d