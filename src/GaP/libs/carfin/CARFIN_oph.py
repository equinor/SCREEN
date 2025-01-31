""" builder with open hole sections
"""
from typing import TextIO

def CARFIN_oph(ID: float,
                x_min_oph: int, x_max_oph: int,
                y_min_oph: int, y_max_oph: int,
                k_min_hole: int, k_max_hole: int,
                perm: float,
                LGR_NAME: str,
                O: TextIO):  # noqa: E741
    """ CARFIN for open hole sections

        The open hole sections can be modelled the same as pipe, but without zero transmissibility around the high perm. area 
        to allow moving of fluids side ways from the oph. This is particularly important in the cases where there is a 
        drilled but uncased hole in the setting. 

        The SATNUM = 2 is added to prosperities change. The idea is to have linear rel.perms to the second saturation table, so that 
        there will be least resistance for flow in the free oph. 

        Args:
            ID (float): Internal Diameter (m)
            x_min_oph (int): minimum x
            x_max_oph (int): maximum x
            y_min_oph (int): minimum y
            y_max_oph (int): maximum y
            k_min_hole (int): minimum k of open hole section
            k_max_hole (int): maximum k of open hole section
            perm (float): permeability value
            LGR_NAME (str): LGR name
            O (TextIO): opened file handle

    """
    
    print ('EQUALS',file=O)

    print ('--Open-hole section with ID of',ID*39.37,'and perm of',perm,' were set in',LGR_NAME, 'Local Grid refinement',file=O)
    print ('PERMX','',perm,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PERMY','',perm,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PORO','','0.99','',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    
    print ('SATNUM','',2,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('FIPLEG','',6,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('EQLNUM','',2,'',x_min_oph,'',x_max_oph,'',y_min_oph,'',y_max_oph,'',k_min_hole,'',k_max_hole,'','/',file=O)

    print ('/',file=O)
