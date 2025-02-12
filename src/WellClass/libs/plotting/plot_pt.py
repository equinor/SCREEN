
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

from ..pvt.pvt import get_pvt
from ..well_pressure.pressure import Pressure

'''Global names. Should be replaced by a global class containing these names? TODO'''
SF_DEPTH_NAME     = 'sf_depth_msl'
DEPTH_NAME        = 'depth_msl'
MAX_PRESSURE_NAME = 'max_pressure'
RHO_NAME          = 'rho'



def plot_pt(my_pressure: Pressure, 
            fig : mpl.figure.Figure = None, 
            ax : plt.Axes =None, 
            file_only=False, 
            file_name="pt",
            plot_HSP:bool = False, 
            plot_Shmin:bool = False, 
            plot_RP:bool = True, 
            plot_MSAD:bool = False, 
            plot_maxP:bool = False):    
     
    """ 
    pressure vs temperature
    Takes the presssure class and plots pressure vs temperature.
    Background of the image is colored by the fluid density

    my_pressure: pressure class
    fig: matplotlib fig object
    ax: matploltib ax object
    file_only: boolean to print the image to file instead of screen
    file_name: preffix of file name
    plot_HSP to plot brine hydrostatci pressure
    plot_RP to plot reservoir pressure scenarios
    plot_MSAD top plot Minimum Safatey Abandonement pressure for each reservoir scenario
    plot_maxP to plot max pressurization at a given deth
    """

    if fig is None:
        fig, ax = plt.subplots()


    t, p, rho_co2, rho_h2o = get_pvt(my_pressure.pvt_path)

    #Plot density colormap
    rho_pcm = ax.pcolormesh(t, p, rho_co2, alpha=0.5)

    #Plot phase boundary and critical point
    t_co2 = np.array([-50,-48.35,-46.69,-45.04,-43.38,-41.73,-40.08,-38.42,-36.77,-35.11,-33.46,-31.81,-30.15,-28.5,-26.84,-25.19,-23.53,-21.88,-20.23,-18.57,-16.92,-15.26,-13.61,-11.96,-10.3,-8.65,-6.99,-5.34,-3.69,-2.03,-0.38,1.28,2.93,4.58,6.24,7.89,9.55,11.2,12.86,14.51,16.16,17.82,19.47,21.13,22.78,24.43,31.05])
    p_co2 = np.array([6.8,7.27,7.77,8.29,8.83,9.4,10,10.63,11.28,11.97,12.68,13.43,14.21,15.02,15.87,16.75,17.66,18.62,19.61,20.64,21.7,22.81,23.96,25.15,26.38,27.66,28.98,30.34,31.76,33.21,34.72,36.28,37.89,39.54,41.25,43.01,44.83,46.7,48.63,50.61,52.65,54.75,56.91,59.12,61.4,63.75,73.76])
    ax.plot(t_co2, p_co2, color='k', lw=1.5, label = r'$CO_2$ phase env.')
    ax.scatter(t_co2.max(), p_co2.max(), c='k')

    #Retrieve pressures as well
    # if not hasattr(my_pressure, "pressure_CO2"):
    #     my_pressure._compute_CO2_pressures()
    pt_df = my_pressure.pressure_CO2

    wd = my_pressure.header['sf_depth_msl']  # noqa: F841
    co2_datum = my_pressure.co2_datum  # noqa: F841

    #Plot fluid pressure scenarios
    ls_list = ['solid','dashed','dashdot', 'dotted']
    counter = 0

    if plot_HSP:
        pt_df['init'].plot(y='hs_p', x='temp', ax=ax, label='$p_{hs}$', color='steelblue', lw = 0.75)

    if plot_Shmin:
        pt_df['init'].plot(x='temp', y='Shmin', ax=ax, label='$p_{hs}$', color='k', lw = 0.75)

    ymax = 0
    # for key in my_pressure.reservoir_P:
    #         if key != 'depth_msl':
    #                 pt_df.query('depth_msl>=@wd').plot(y=key+'_h2o', x='temp', ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])
    #                 pt_df.query('depth_msl>=@wd').plot(y=key+'_co2', x='temp', ax=ax, label = f'$CO_2$ {key}', color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])
                    
    #                 base_msl = pt_df.query('depth_msl>(@co2_datum)+50')[key+'_h2o'].iloc[0]

    #                 if base_msl > ymax:
    #                         ymax = base_msl

    #                 counter+=1
    #                 counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter


    # #Plot max pressure cases
    # counter = 0
    # for key in pt_df.columns: 
    #     if key.startswith(MAX_PRESSURE_NAME) and RHO_NAME not in key:
    #         colname = f"{key}"
    #         pt_df.query('depth_msl>=@wd').plot(y=colname, x='temp', ax=ax, label = colname, color='green', legend=True, lw = 0.75, ls=ls_list[counter])
    #         base_msl = pt_df.query('depth_msl>(@co2_datum)+50')[colname].iloc[0]

    #         if base_msl > ymax:
    #             ymax = base_msl

    #         counter+=1
    #         counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter  


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

        sc_msad_temp = np.interp(float(sc_msad_z), pt_df[('init','depth_msl')], pt_df[('init','temp')])


        #plot co2 gradient
        pt_df[pt_df[('init', 'depth_msl')]>=wd].plot(y=(sc_name, 'co2'), x=('init', 'temp'), ax=ax, label = f'$CO_2$ {sc_name}', color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])

        #plot water gradient
        pt_df[pt_df[('init', 'depth_msl')]>=wd].plot(y=(sc_name, 'h2o'), x=('init', 'temp'), ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])


        if plot_MSAD:
            ax.scatter(sc_msad_temp, sc_msad_p, color='firebrick')

        #Find deepest point to display
        base_msl = pt_df[pt_df[('init', 'depth_msl')]>co2_datum+50][(sc_name, 'h2o')].iloc[0]

        if base_msl > ymax:
            ymax = base_msl


        counter+=1
        counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter  
        
  


    xmax = pt_df['init'].query('depth_msl>(@co2_datum)+50')['temp'].iloc[0]
    #xmax = pt_df['temp'].max()

    ax.set_ylabel(r'p [bar]')
    ax.set_xlabel(r'T [$\degree$C]')
    ax.set_xlim(1, xmax)
    ax.set_ylim(1, ymax)
    fig.colorbar(rho_pcm, label=r'$\rho_{CO_2}$ [$kg/m^3$]')

    fig.tight_layout()

    if file_only:
      plt.savefig(f'{file_name}.png')
    else:
        plt.show()
