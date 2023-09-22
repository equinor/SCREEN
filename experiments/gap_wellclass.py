
""" To run it, type the following:

$ python -m experiments.gap_wellclass -p ./test_data/examples/smeaheia_v1 -w smeaheia.yaml -s GEN_NOLGR_PH2 --plot --ali-way 

for comparing the output from smeaheia data with the output using Ali's grid logic.

Otherwise, for other examples,

# 1. smeaheia_v1

$ python -m experiments.gap_wellclass --sim-path ./test_data/examples/smeaheia_v1 --well smeaheia.yaml --sim-case GEN_NOLGR_PH2 --plot 

# 2. smeaheia_v2

$ python -m experiments.gap_wellclass --sim-path ./test_data/examples/smeaheia_v2 --well smeaheia.yaml --sim-case TEMP-0 --plot

# 3. cosmo

$ python -m experiments.gap_wellclass --sim-path ./test_data/examples/cosmo --well cosmo.yaml --sim-case TEMP-0 --plot

"""

import os
import json

import argparse
import pathlib

from src.WellClass.libs.utils import (
    csv_parser,
    yaml_parser,
)

# WellClass
from src.WellClass.libs.well_class import Well

from src.WellClass.libs.grid_utils import (
    WellDataFrame,
    GridCoarse,
    GridRefine,
    LGRBuilder,
)

# plots
from src.WellClass.libs.plotting import (
    plot_grid,
)

def main(args):

    ############# 0. User options ######################

    # TODO(hzh): use Ali's grid logic
    Ali_way = args.ali_way

    # where the location for the input parameters and eclipse .EGRID and .INIT files
    # configuration path, for example './test_data/examples/smeaheia_v1'
    sim_path = pathlib.Path(args.sim_path)

    # input configuration file name, for example, 'smeaheia.yaml'
    well_config = pathlib.Path(args.well)

    # extract suffix
    suffix = well_config.suffix
    # .yaml or .csv?
    use_yaml = suffix in ['.yaml', '.yml']

    # location of .egrid, for example, TEMP-0.EGID, etc.
    simcase = sim_path/args.sim_case

    # output directory
    output_dir = pathlib.Path(args.output_dir)
    # LRG name 
    LGR_NAME = args.output_name

    ############ 2. Load well configuration file ###############

    # where well configuration file is located
    well_name = sim_path/well_config
    
    if use_yaml:
        
        # # pydantic model
        well_model = yaml_parser(well_name)
        well_csv = json.loads(well_model.spec.model_dump_json())
    else:

        # load the well information
        well_csv = csv_parser(well_name)

    ########### 3. build Well class ######################

    # build well class
    my_well = Well( header       = well_csv['well_header'], 
                    drilling     = well_csv['drilling'],
                    casings      = well_csv['casing_cement'],
                    geology      = well_csv['geology'],
                    barriers     = well_csv['barriers'], 
                    barrier_perm = well_csv['barrier_permeability'],
                    co2_datum    = well_csv['co2_datum'],
            )

    # to well dataframe
    well_df = WellDataFrame(my_well)

    # for convenience

    # extract dataframes
    annulus_df = well_df.annulus_df
    drilling_df = well_df.drilling_df
    casings_df = well_df.casings_df
    borehole_df = well_df.borehole_df

    barriers_mod_df = well_df.barriers_mod_df

    ############### 4. various grids #####################

    ##### 4.1 grid_coarse 

    # Loading the model from .EGRID and .INIT
    grid_coarse = GridCoarse(str(simcase))

    ##### 4.2 LGR grid 

    # LGR grid information in x, y, z directions
    lgr = LGRBuilder(grid_coarse, 
                     annulus_df, 
                     drilling_df, casings_df, borehole_df,
                     Ali_way)

    ##### 4.3 grid refine 
    
    # Set up dataframe for LGR mesh
    grid_refine = GridRefine(grid_coarse,
                            lgr.LGR_sizes_x, lgr.LGR_sizes_y, 
                            lgr.LGR_sizes_z, 
                            )

    ############### 5. build LGR #####################

    ##### 5.1 compute bounding box 

    # Bounding box for well elements
    well_df.compute_bbox(grid_refine.mesh_df, grid_refine.nx)

    ##### 5.2 set up material type 

    # set up material type
    grid_refine.set_material_type(drilling_df,
                                  casings_df, 
                                  barriers_mod_df)
    
    ##### 5.3 set up permeability 

    # set up permeability
    grid_refine.set_permeability(drilling_df, casings_df, barriers_mod_df)

    ########### 6. output grdecl file ###################

    # Write LGR file
    lgr.build_grdecl(output_dir, LGR_NAME,
                     drilling_df,
                     casings_df,
                     barriers_mod_df)
    
    # for qc
    if args.plot:
        plot_grid(my_well, grid_coarse)
        plot_grid(my_well, grid_refine)

if __name__ == '__main__':

    # Create the parser
    parser = argparse.ArgumentParser()

    parser.add_argument("--ali-way", action="store_true",
                        help="Use Ali's logic to generate LGR grids")

    parser.add_argument('-p', "--sim-path", type=str, required=True,
                        help='The file path to the configuration folder')
    
    parser.add_argument('-w', "--well", type=str, required=True,
                        help="input well configuration file name, can be .yaml or .csv format")

    parser.add_argument('-s', "--sim-case", type=str, required=True,
                        help="file path of simulation case")
            
    parser.add_argument('--output-dir', type=str, default='./experiments',
                        help="output directory")
    parser.add_argument('--output-name', type=str, default='LEG_HIRES', 
                        help='output file name')
    
    parser.add_argument('--plot', action='store_true', help='plot well sketch and well grids')

    # Parse the argument
    args = parser.parse_args()

    main(args)

