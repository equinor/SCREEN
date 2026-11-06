""" barrier builder 
"""
from typing import TextIO

def CARFIN_barrier(ID: float, 
                     x_min_bar: int, x_max_bar: int,
                     y_min_bar: int, y_max_bar: int,
                     k_min_bar: int, k_max_bar: int,
                     perm: float,
                     LGR_NAME: str, 
                     O: TextIO):  # noqa: E741
    """ CARFIN for barrier
    
        The barriers can be mimicked by very low permeability with the same size of pipe ID and have their own start and end depth. 

        Args:
            ID (float): Internal Diameter (m)
            x_min_bar (int): minimum x
            x_max_bar (int): maximum x
            y_min_bar (int): minimum y
            y_max_bar (int): maximum y
            k_min_bar (int): minimum k
            k_max_bar (int): maximum k
            perm (float): permeability value
            LGR_NAME (str): LGR name
            O (TextIO): opened file handle
    """

    print ('EQUALS',file=O)

    print ('--barrier with ID of',ID*39.37,'and perm of',perm,' were set in',LGR_NAME, file=O)
    print ('PERMX','',perm,'',x_min_bar,'',x_max_bar,'',y_min_bar,'',y_max_bar,'',k_min_bar,'',k_max_bar,'','/',file=O)
    print ('PERMY','',perm,'',x_min_bar,'',x_max_bar,'',y_min_bar,'',y_max_bar,'',k_min_bar,'',k_max_bar,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_bar,'',x_max_bar,'',y_min_bar,'',y_max_bar,'',k_min_bar,'',k_max_bar,'','/',file=O)
    print ('PORO','','0.01','',x_min_bar,'',x_max_bar,'',y_min_bar,'',y_max_bar,'',k_min_bar,'',k_max_bar,'','/',file=O)
    print ('SATNUM','',1,'',x_min_bar,'',x_max_bar,'',y_min_bar,'',y_max_bar,'',k_min_bar,'',k_max_bar,'','/',file=O)
    
    print ('/',file=O)
