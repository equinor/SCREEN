""" pipe builder
"""
from typing import TextIO

from ..free_fluid import FREE_FLUID_PORO

def CARFIN_pipe(ID: float,
                x_min_pipe: int, x_max_pipe: int,
                y_min_pipe: int, y_max_pipe: int,
                k_min_pipe: int, k_max_pipe: int,
                perm: float,
                LGR_NAME: str, 
                O: TextIO,  # noqa: E741
                poro: float = FREE_FLUID_PORO):
    """ CARFIN for pipe

        The pipes can be mimicked by a very narrow (in the size of ID of a pipe-20 to 50 cm) and high permeability grids. 
        Those grids could be surrounded by grids with zero transmissibility. 

        Args:
            ID (float): Internal Diameter (m)
            x_min_pipe (int): minimum x
            x_max_pipe (int): maximum x
            y_min_pipe (int): minimum y
            y_max_pipe (int): maximum y
            k_min_pipe (int): minimum k
            k_max_pipe (int): maximum k
            perm (float): permeability value
            poro (float): porosity value
            LGR_NAME (str): LGR name
            O (TextIO): opened file handle
    """

    print ('EQUALS',file=O)
    print ('--pipe with ID of',ID*39.37,'and perm of',perm,' were set in',LGR_NAME, 'Local Grid refinement',file=O)
    print ('PERMX','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('PERMY','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('PORO','',poro,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    print ('--Transmisibilities of the edge of the pipe set to zero',file=O)
    print ('MULTX','',0,'',x_min_pipe,'',x_min_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTX','',0,'',x_max_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTX','',0,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_min_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTX','',0,'',x_min_pipe,'',x_max_pipe,'',y_max_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    print ('MULTY','',0,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_min_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTY','',0,'',x_min_pipe,'',x_max_pipe,'',y_max_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTY','',0,'',x_min_pipe,'',x_min_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTY','',0,'',x_max_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    print ('--New Saturation region for flow in pipe',file=O)
    print ('SATNUM','',2,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('/',file=O)
