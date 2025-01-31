""" cement bond builder
"""
from typing import TextIO

def CARFIN_cement_bond(ID: float, 
                        x_min_pipe: int, x_max_pipe: int,
                        y_min_pipe: int, y_max_pipe: int,
                        k_min_CB: int, k_max_CB: int,
                        *,
                        x_bd=1, y_bd=1,
                        perm: float,
                        LGR_NAME: str, 
                        O: TextIO):  # noqa: E741
    """ CARFIN for cement bond
    
        The cement bond can be mimicked by low perm vertical layer adjustment to the casing with given depth and interval. 

        Args:
            ID (float): Internal Diameter (m), only for comments, not used in calculation
            x_min_pipe (int): minimum x for actual internal open hole
            x_max_pipe (int): maximum x for actual internal open hole
            y_min_pipe (int): minimum y for actual internal open hole
            y_max_pipe (int): maximum y for actual internal open hole
            k_min_CB (int): minimum k for actual internal open hole
            k_max_CB (int): maximum k for actual internal open hole
            x_bd (int): x thickness for out extension, default: 1
            y_bd (int): y thickness  for out extension, default: 1
            perm (float): permeability value
            LGR_NAME (str): LGR name
            O (TextIO): opened file handle
    """

    print ('EQUALS',file=O)

    print ('--cement around pipe with ID of',ID*39.37,' and perm of',perm,' were set in',LGR_NAME,file=O)
    print ('--Top side',file=O)
    print ('PERMX','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMY','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PORO','', 0.01,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('FIPLEG','',6,'',  x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('EQLNUM','',1,'',  x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_min_pipe-y_bd,'',y_min_pipe-1,'',k_min_CB,'',k_max_CB,'','/',file=O)

    print ('',file=O)

    print ('--Bottom side',file=O)
    print ('PERMX','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMY','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PORO','', 0.01,'',x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('FIPLEG','',6,''  ,x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('EQLNUM','',1,''  ,x_min_pipe-x_bd,'',x_max_pipe+x_bd,'',y_max_pipe+1,'',y_max_pipe+y_bd,'',k_min_CB,'',k_max_CB,'','/',file=O)

    print ('',file=O)

    print ('--Left side',file=O) 
    print ('PERMX','',perm,'',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMY','',perm,'',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PORO','', 0.01,'',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('FIPLEG','',6,  '',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('EQLNUM','',1,  '',x_min_pipe-x_bd,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)

    print ('--Right side',file=O)

    print ('PERMX','',perm,'',x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMY','',perm,'',x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PERMZ','',perm,'',x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('PORO','', 0.01,'',x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('FIPLEG','',6,''  ,x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)
    print ('EQLNUM','',1,''  ,x_max_pipe+1,'',x_max_pipe+x_bd,'',y_min_pipe,'',y_max_pipe,'',k_min_CB,'',k_max_CB,'','/',file=O)

    print ('/',file=O)
