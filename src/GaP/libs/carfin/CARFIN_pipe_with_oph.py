""" pipe builder with open hole sections
"""
from typing import TextIO

def CARFIN_pipe_with_oph(ID: float,
                            x_min_pipe: int, x_max_pipe: int,
                            y_min_pipe: int, y_max_pipe: int,
                            k_min_pipe: int, k_max_pipe: int,
                            k_min_hole: int, k_max_hole: int,
                            perm: float,
                            LGR_NAME: str,
                            O: TextIO):  # noqa: E741
    """ CARFIN for pipe with open hole sections

        The pipes can be mimicked by a very narrow (in the size of ID of a pipe-20 to 50 cm) and high permeability grids. 
        Those grids could be surrounded by grids with zero transmissibility. 

        The open hole sections can be modelled the same as pipe, but without zero transmissibility around the high perm. area 
        to allow moving of fluids side ways from the piper. This is particularly important in the cases where there is a 
        drilled but uncased hole in the setting. 

        First the pipe (high) permeabilities are assigned to the whole pipe ( casing + openhole section) because both casing and 
        openhole are sharing the highest permeability inner  most layer.

        The SATNUM = 2 is added to prosperities change. The idea is to have linear rel.perms to the second saturation table, so that 
        there will be least resistance for flow in the free pipe. 

        Then to mimic the pipe, there should be no flow on the side ways, therefore, the transmisibilities in the X and Y directions 
        in the edge of the pipe are set to zero. 

        Args:
            ID (float): Internal Diameter (m)
            x_min_pipe (int): minimum x
            x_max_pipe (int): maximum x
            y_min_pipe (int): minimum y
            y_max_pipe (int): maximum y
            k_min_pipe (int): minimum k of pipe
            k_max_pipe (int): maximum k of pipe
            k_min_hole (int): minimum k of open hole section
            k_max_hole (int): maximum k of open hole section
            perm (float): permeability value
            LGR_NAME (str): LGR name
            O (TextIO): opened file handle

    """
    
    print ('EQUALS',file=O)

    print ('--pipe with ID of',ID*39.37,'and perm of',perm,' were set in',LGR_NAME, 'Local Grid refinement',file=O)
    print ('PERMX','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PERMY','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PERMZ','',perm,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('PORO','','0.99','',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('SATNUM','',2,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)
    print ('--FIPLEG (FIPNUM) defintion',file=O)
    print ('FIPLEG','',6,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)

    print ('--EQLNUM defintion',file=O)
    print ('EQLNUM','',2,'',x_min_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_hole,'',k_max_hole,'','/',file=O)


    print ('--Transmisibilities of the edge of the pipe set to zero',file=O)
    print ('MULTX','',0,'',x_min_pipe-1,'',x_min_pipe-1,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTX','',0,'',x_max_pipe,'',x_max_pipe,'',y_min_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    # # TODO(hzh): Not sure about the next two lines of codes
    # print ('MULTX','',0,'',x_min_pipe-1,'',x_max_pipe,'',y_min_pipe-1,'',y_min_pipe-1,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    # print ('MULTX','',0,'',x_min_pipe-1,'',x_max_pipe,'',y_max_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    print ('MULTY','',0,'',x_min_pipe-1,'',x_max_pipe,'',y_min_pipe-1,'',y_min_pipe-1,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    print ('MULTY','',0,'',x_min_pipe-1,'',x_max_pipe,'',y_max_pipe,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    # # TODO(hzh): Not sure about the next two lines of codes    
    # print ('MULTY','',0,'',x_min_pipe-1,'',x_min_pipe-1,'',y_min_pipe-1,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)
    # print ('MULTY','',0,'',x_max_pipe,'',x_max_pipe,'',y_min_pipe-1,'',y_max_pipe,'',k_min_pipe,'',k_max_pipe,'','/',file=O)

    print ('/',file=O)
