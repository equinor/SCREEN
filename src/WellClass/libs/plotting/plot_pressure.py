
import pandas as pd
import matplotlib.pyplot as plt 
import numpy as np

from typing import Union
from ..well_pressure import Pressure

'''Global names. Should be replaced by a global class containing these names? TODO'''
SHMIN_NAME        = 'Shmin'
SF_DEPTH_NAME     = 'sf_depth_msl'
DEPTH_NAME        = 'depth_msl'
MAX_PRESSURE_NAME = 'max_pressure'
RHO_NAME          = 'rho'

def plot_pressure(my_pressure: Pressure, 
                  geology_dict: dict, barriers: dict, ax=None, 
                  plot_HSP:bool = True, 
                  plot_RP:bool = True, 
                  plot_MSAD:bool = True, 
                  plot_maxP:bool = True):
    """
    pressure vs depth
    Takes the Pressure class, geology and barriers tables
    plot_HSP to plot brine hydrostatci pressure
    plot_RP to plot reservoir pressure scenarios
    plot_MSAD top plot Minimum Safatey Abandonement pressure for each reservoir scenario
    plot_maxP to plot max pressurization at a given deth
    """

    if ax is None:
            fig, ax = plt.subplots()
        
#     if not hasattr(my_pressure, "pressure_CO2"):
#         my_pressure._compute_CO2_pressures()

    pt_df = my_pressure.pressure_CO2

    well_header = my_pressure.header
    sf_depth    = well_header['sf_depth_msl']
    
    barriers_df = pd.DataFrame(barriers)
    geology_df  = pd.DataFrame(geology_dict)
    
    #define plot spatial references
    base_deepest_rsrv = geology_df[geology_df.reservoir_flag]['base_msl'].max()
    ymax = max([base_deepest_rsrv,my_pressure.co2_datum])+100
    xmax = pt_df['init'].query('depth_msl>@ymax')['Shmin'].iloc[0]
    xmin = 0
    
    # Draw cement plugs
    for idx, row in barriers_df.iterrows():
        barrier = ax.axhspan(row['top_msl'], row['bottom_msl'], color='lightgray', zorder=-20, label = 'cement plug')

    #Plot hydrostatic pressure gradient
    if plot_HSP:
        pt_df['init'].plot(x='hs_p', y='depth_msl', ax=ax, label='$p_{hs}$', color='steelblue', lw = 0.75)

    #Plot minimum horizontal stress
    pt_df['init'].plot(x='Shmin', y='depth_msl', ax=ax, label=r'$\sigma_{h min}$', color='k', lw = 0.75)

    #Plot fluid pressure scenarios
    ls_list = ['solid','dashed','dashdot', 'dotted']

    #Read pressure scenarios
    scenarios = pd.DataFrame(my_pressure.pressure_scenarios).T

    #Filter scenarios based on boolean type
    if plot_RP and not plot_maxP:
        scenarios = scenarios.query('type == "reservoir"')
    elif plot_maxP and not plot_RP:
        scenarios = scenarios.query('type == "max_p"')

    #iterate over scenarios
    counter = 0
    for idx, p_sc in scenarios.iterrows():
        sc_type    = p_sc['type']
        sc_name    = p_sc['name']
        sc_msad_p  = p_sc['p_MSAD']
        sc_msad_z  = p_sc['z_MSAD']
        sc_delta_p = p_sc['p_delta']

        #define legend if it is a reservoir pressure scenario
        if sc_type == 'reservoir':
            sc_label = rf'$CO_2$ P ($\Delta$P = {sc_delta_p:.0f} bar)'

        #define legend if it is a maximum pressure scenario
        elif sc_type == 'max_p':
            sc_label = rf'max $CO_2$ P to ($\Delta$P = {sc_delta_p:.0f} bar)'
        
        #include MSAD
        if plot_MSAD:
            if ~np.isnan(sc_msad_z):
                sc_label = f'{sc_label}\nMSAD = {sc_msad_z:.0f} mTVDMSL'
            
            ax.scatter(sc_msad_p, sc_msad_z, color='firebrick')

        #plot water gradient
        pt_df[pt_df[('init', 'depth_msl')]>=sf_depth].plot(x=(sc_name, 'h2o'), y=('init', 'depth_msl'), ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])

        #plot CO2 gradient
        pt_df[pt_df[('init', 'depth_msl')]>=sf_depth].plot(x=(sc_name, 'co2'), y=('init', 'depth_msl'), ax=ax, label = sc_label, color='firebrick', legend=False, lw = 0.75, ls=ls_list[counter])
        counter+=1
        counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter  
        
            

    #Optimize legend
    ax.legend()
    handles, labels = ax.get_legend_handles_labels()  
    lgd = dict(zip(labels, handles))
    ax.legend(lgd.values(), lgd.keys())
    
    ax.set_xlim(xmin, xmax)
    ax.set_xlabel('pressure [bar]')
    ax.set_ylim(0, ymax)
    ax.invert_yaxis()

    if 'fig' in locals():
            return fig, ax
    else:
            return ax
