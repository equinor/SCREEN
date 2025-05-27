import os
import json
import pathlib
import pandas as pd
import numpy as np
from datetime import datetime
from matplotlib import pyplot as plt
from matplotlib import rcParams
from matplotlib import font_manager

import sys
code_path = os.path.abspath("../")
sys.path.append(code_path)
from src.WellClass.libs.utils import csv_parser, yaml_parser
from src.WellClass.libs.well_class import Well
from src.WellClass.libs.well_pressure import Pressure
from src.WellClass.libs.grid_utils import WellDataFrame, GridLGR, LGRBuilder
from src.WellClass.libs.plotting import plot_grid, plot_sketch, plot_pressure
from src.GaP.libs.aux_functions.aux_func_cirrus_eql import setup_equilibration

# User inputs
root_input_folder = '../test_data/examples/wildcat-pflotran'
root_output_folder = '../test_data/examples/wildcat-pflotran'
well_input_file = 'smeaheia.yaml'
# well_input_file = 'wildcat.yaml'
start_date = datetime(2025, 1, 1)  # Simulation start date
end_date = datetime(2125, 1, 1) # Simulation end date
show_well_sketch = True
scenario_idx = 1  # Pressure scenario index (by default 0)
sim_case_name = 'ALPHA'
LGR_NAME = 'LW_LGR'

# template and constant files
template_simcase = 'TEMP-0'
pvt_path = '../test_data/pvt_constants/'
Ali_way = False

# Configuration
input_sim_path = pathlib.Path(root_input_folder)
well_input = pathlib.Path(well_input_file)
output_sim_path = pathlib.Path(root_output_folder)
file_extension = well_input.suffix
use_yaml = file_extension in ['.yaml', '.yml']

# Paths
template_model_dir = input_sim_path / 'model'
template_include_dir = input_sim_path / 'include'
temp_simcase = template_model_dir / template_simcase #template PFLOTRAN file
template_grdecl = template_include_dir / 'TEMP_GRD.grdecl'

co2_database = template_include_dir / r'co2_db_new.dat'

output_model_dir = output_sim_path / 'model'
output_include_dir = output_sim_path / 'include'

output_simcase = output_model_dir / sim_case_name
output_simcase_grdecl = output_include_dir / f'{sim_case_name}_GRD.grdecl'


############ Copy template files and update based on user inputs ######################

# Create directories if they do not exist
output_model_dir.mkdir(parents=True, exist_ok=True)
output_include_dir.mkdir(parents=True, exist_ok=True)

# Read and modify template files
# Update template GRDECL file
with open(template_grdecl) as file:
    lines = file.readlines()
lines[5] = f'--{lines[5]}'  # comment out line to include LGR grdecl file
with output_simcase_grdecl.open('w') as file:
    file.writelines(lines)

# Copy CO2 database to output include directory
output_co2_database = output_include_dir / co2_database.name
with open(co2_database, 'r') as src, open(output_co2_database, 'w') as dst:
    dst.write(src.read())

with open(temp_simcase.with_suffix('.in')) as file:
    lines = file.readlines()

title = f'{sim_case_name} LEGACY Well SCREEN simulation'
lines[1] = f'!{title}\n'
lines[34] = f' START_DATE  {start_date.strftime("%d %b %Y").upper()}\n'   #Set start date
lines[35] = f' FINAL_DATE  {start_date.strftime("%d %b %Y").upper()} \n'  #Set end date equal to start date so only equilibration is run
lines[23] = f'  TYPE grdecl ../include/{output_simcase_grdecl.name} \n'          #Update grdecl file include path to new one

with output_simcase.with_suffix('.in').open('w') as file:
    file.writelines(lines)

############ Load Well Data - Config file and visualize ################################

# Load well configuration file
well_file_path = input_sim_path / well_input
if use_yaml:
    well_model = yaml_parser(well_file_path)
    well_csv = json.loads(well_model.spec.model_dump_json())
else:
    well_csv = csv_parser(well_file_path)

# Build Well class
my_well = Well(
    header=well_csv['well_header'],
    drilling=well_csv['drilling'],
    casings=well_csv['casing_cement'],
    geology=well_csv['geology'],
    barriers=well_csv['barriers'],
    barrier_perm=well_csv['barrier_permeability'],
    co2_datum=well_csv['co2_datum'],
)

# Retrieve dataframes for easier indexation
well_df = WellDataFrame(my_well)
annulus_df = well_df.annulus_df
drilling_df = well_df.drilling_df
casings_df = well_df.casings_df
borehole_df = well_df.borehole_df
barriers_mod_df = well_df.barriers_mod_df

# Compute Pressure scenarios
my_pressure = Pressure(
    header=well_csv['well_header'],
    reservoir_P=well_csv['reservoir_pressure'],
    co2_datum=well_csv['co2_datum'],
    pvt_path=pvt_path,
)

# Plot sketch and pressures
fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True, figsize=(10, 8))
plot_sketch(my_well, draw_open_hole=False, ax=ax1)
plot_pressure(
    my_pressure, my_well.geology, my_well.barriers, ax=ax2,
    plot_HSP=True, plot_RP=True, plot_MSAD=True, plot_maxP=True
)
fig.tight_layout()
fig.subplots_adjust(wspace=0)

fig.savefig(output_sim_path / f'well_sketch_{well_input.stem}.png')

if show_well_sketch:
	plt.show()
    
############ Write PFT *in files based on Well input ####################################

# Retrieve reference depths
top_reservoir = well_df.geology_df.query('reservoir_flag == True')['top_msl'].min()  # Top reservoir depth
top_overburden = my_well.header['sf_depth_msl'] # Top overburden depth
tops_offset = 4 #Default 4 m offset so the mesh does not start at 0 mMSL

# Compute thicknesses and dz 
water_column_thickness = top_overburden
coarse_overburden_thickness = (top_reservoir - top_overburden) - 5 
reservoir_cell_thickness = 5 
grid_water_thickness = water_column_thickness - tops_offset
grid_coarse_thickness = (top_reservoir - top_overburden) - reservoir_cell_thickness

cells_overburden_dz = grid_coarse_thickness // 9
cell_overbuden_dz_top = grid_coarse_thickness - (cells_overburden_dz * 8)

# Write the tops file
tops_file = output_include_dir / 'tops_dz.inc'
with open(tops_file, 'w') as f:
    f.write("EQUALS\n")
    f.write("TOPS 4 4* 1 1 /\n")
    f.write("/\n\n")
    f.write("DZ\n")
    f.write(f"400*{grid_water_thickness} 400*{cell_overbuden_dz_top} 3200*{cells_overburden_dz} 28000*{reservoir_cell_thickness} /\n")
    f.write("/\n")

# Equilibration section
scenario_name = my_pressure.pressure_scenarios[scenario_idx]['name']

# Reservoir equilibration - Retrieve depth and interpolate pressure
reservoir_wgc_d = my_well.co2_datum  # Retrieve depth of gas-water contact
reservoir_datum_d = reservoir_wgc_d  # Set datum to gas-water contact
reservoir_pressure = np.interp(reservoir_wgc_d, my_pressure.pressure_CO2['init']['depth_msl'], my_pressure.pressure_CO2[scenario_name]['h2o'])

# Overburden equilibration - Retrieve depth and interpolate pressure
overburden_datum_d = 500
overburden_pressure = my_pressure.pressure_CO2['init'].loc[500]['hs_p']

# Generate temperature table
sf_temp = my_well.header['sf_temp'] #Seafloor temperature
geo_tgrad = my_well.header['geo_tgrad'] #Geothermal gradient
sf_depth_msl = my_well.header['sf_depth_msl'] #Seafloor depth

#Depth values in RTMEPVD
z_top_RTEMPVD = tops_offset #Top of RTEMPVD set as tops offset
z_sf_RTEMPVD = sf_depth_msl #Include seafloor depth in RTEMPVD
z_bottom_RTEMPVD = grid_water_thickness + cell_overbuden_dz_top + (cells_overburden_dz * 8) + (reservoir_cell_thickness * 70) + tops_offset

#Temperature values in RTEMPVD
z_RTEMPVT = np.linspace(z_sf_RTEMPVD, z_bottom_RTEMPVD, 8)
z_RTEMPVT = np.insert(z_RTEMPVT, 0, z_top_RTEMPVD)
temp_RTEMPVT = sf_temp + (z_RTEMPVT - sf_depth_msl) * geo_tgrad / 1000
temp_RTEMPVT[z_RTEMPVT <= sf_depth_msl] = sf_temp
new_rtempvd_section = "RTEMPVD\n    ! Metric\n"
for z, t in zip(z_RTEMPVT, temp_RTEMPVT):
    new_rtempvd_section += f"{z:11.2f} {t:8.2f}\n"

# Open CIRRUS input file and update equilibration section
with open(output_simcase.with_suffix('.in')) as file:
    lines = file.readlines()

equil_pmts = {
    'overburden_water': {
        'DATUM_D': overburden_datum_d,
        'PRESSURE': overburden_pressure,
        'WGC_D': None
    },
    'CO2_column': {
        'DATUM_D': reservoir_datum_d,
        'PRESSURE': reservoir_pressure,
        'WGC_D': reservoir_wgc_d
    }
}

new_lines = lines[:236]
for name, pmts in equil_pmts.items():
    equil_lines = setup_equilibration(name=name, pressure=pmts['PRESSURE'], d_datum=pmts['DATUM_D'], wgc_d=pmts['WGC_D'], rtempvd=new_rtempvd_section, top=z_top_RTEMPVD, bottom=z_bottom_RTEMPVD)
    new_lines += equil_lines
new_lines += lines[316:]

with output_simcase.with_suffix('.in').open('w') as file:
    file.writelines(new_lines)

############ Run coarse simulation to retrieve EGRID file and build LGR ##################
# Run coarse simulation
run_config_coarse = output_simcase.with_suffix('.in')
os.system(f"runcirrus -i -nm 6 {run_config_coarse}")

# Build LGR
lgr = LGRBuilder(output_simcase, annulus_df, drilling_df, Ali_way)
gap_casing_df = lgr.build_grdecl(output_include_dir, LGR_NAME, drilling_df, casings_df, barriers_mod_df)

# Update EQLNUM
top_eql_k = barriers_mod_df.iloc[0]['k_max'] + 1
with open((output_include_dir / LGR_NAME).with_suffix('.grdecl')) as lgr_file:
    lines = lgr_file.readlines()
for idx, line in enumerate(lines):
    if line.startswith('EQLNUM'):
        line_components = line.split()
        keyword, magnitude, i_min, i_max, j_min, j_max, k_min, k_max = line_components[:-1]
        magnitude, i_min, i_max, j_min, j_max, k_min, k_max = map(int, [magnitude, i_min, i_max, j_min, j_max, k_min, k_max])
        if magnitude == 2 and (k_min < top_eql_k and k_max < top_eql_k):
            lines[idx] = f'--{line}'
        elif magnitude == 2 and k_min < top_eql_k:
            lines[idx] = f'{keyword} {magnitude} {i_min} {i_max} {j_min} {j_max} {top_eql_k} {k_max} /\n'
with (output_include_dir / LGR_NAME).with_suffix('.grdecl').open('w') as file:
    file.writelines(lines)

############ Run coarse simulation to retrieve EGRID file and build LGR ##################
# Run LGR simulation
with open(output_simcase_grdecl) as file:
    lines = file.readlines()
lines[5] = f'external_file ../include/{LGR_NAME}.grdecl / \n'
with output_simcase_grdecl.open('w') as file:
    file.writelines(lines)

with open(output_simcase.with_suffix('.in')) as file:
    lines = file.readlines()
lines[35] = f' FINAL_DATE  {end_date.strftime("%d %b %Y").upper()} \n'
with output_simcase.with_suffix('.in').open('w') as file:
    file.writelines(lines)

run_config_lgr = output_simcase.with_suffix('.in')
os.system(f"runcirrus -i -nm 6 {run_config_lgr}")

# Load files from PFLOTRAN simulation
grid_lgr = GridLGR(output_simcase)

# Visualization
grid_coarse = lgr.grid_coarse
plot_grid(my_well, grid_coarse, prop='PERMX')
plt.show()

PROPS = 'EQLNUM'
plot_grid(my_well, grid_lgr, prop=PROPS)
plt.show()