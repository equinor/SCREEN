from well_class_v2 import *


#Import CSV tables
filename = r'Simple_well.csv'

well_csv = csv_parser(filename)

#Process well by running well class
my_well = Well( header       = well_csv['well_header'], 
                drilling     = well_csv['drilling'],
                casings      = well_csv['casing_cement'],
                barriers     = well_csv['barriers'], 
                reservoir_P  = well_csv['reservoir_pressure'],
                main_barrier = well_csv['main_barrier'],
                barrier_perm = well_csv['barrier_permeability'],
                co2_datum    = well_csv['co2_datum'],
                geology      = well_csv['geology'],
           )

#Plot sketch, pressures
fig, (ax1, ax2) = plt.subplots(1,2, sharey=True)
my_well.plot_sketch(ax=ax1)
my_well.plot_pressure(ax=ax2)

fig.tight_layout()

#Plot PT diagram
my_well.plot_PT()

plt.show()
