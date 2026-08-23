'''
How to initialize:
import well_class
INDATA          = <path to a csv-file with the well-data>
well_df         = well_class.csv_parser(INDATA)                          #Reads the csv-file and organize the data into a dict of dataframes

Then the class is initialized with a lot of explicit calls. (Bad structure - should been done in one go: mywell = Well(INDATA))
mywell          = well_class.Well(
                       header       = well_df['well_header'],
                       reservoir_P  = well_df['reservoir_pressure'],
                       drilling     = well_df['drilling'],
                       casings      = well_df['casing_cement'],
                       barriers     = well_df['barriers'],
                       geology      = well_df['geology'],
                       main_barrier = well_df['main_barrier'],
                       barrier_perm = well_df['barrier_permeability'],
                       co2_datum    = well_df['co2_datum']
                   )

Now additional functionalities that can be explicitely called are 
   .plot_pt()
   .plot_pressure()  + plt.show()
   .plot_sketch()    + plt.show()

'''


import pandas as pd
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
import json
import re
import io
from scipy.interpolate import RectBivariateSpline
import scipy.constants
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from itertools import groupby

'''Some global parameters'''
G       = scipy.constants.g   #9.81 m/s2 gravity acceleration
BAR2PA  = scipy.constants.bar #10**5 Going from bars to Pascal: 1 bar = 10**5 Pascal
REGR_A  = -0.000116           #Intercept term in regression equation for the proxy. Consider as a input
REGR_B  = 0.000002725         #Inclination-term in regression equation for the proxy

def get_pvt():
    '''Reads the vectors for pressure and temperature and the matrix for rho
       Note that the values for temperature and rho must be aligned with values in rho
       Note also for rho: One temperature for each column
                          One pressure for each row
    '''
    fn_temp    = "temperature.txt"
    fn_pres    = "pressure.txt"
    fn_rho_co2 = "rho_co2.txt"
    fn_rho_h2o = "rho_h2o.txt"
    t   = np.loadtxt(fn_temp)
    p   = np.loadtxt(fn_pres)
    rho_co2 = np.loadtxt(fn_rho_co2,delimiter=',')
    rho_h2o = np.loadtxt(fn_rho_h2o,delimiter=',')

    return t, p, rho_co2, rho_h2o

def get_hydrostatic_P(well_header, dz=1):
    '''Simple integration to get the hydrostatic pressure at a given depth
       Does also calculates the depth column, temperatur vs depth and water density (RHOH2O) vs depth (hydrostatic)
    '''
    t_vec, p_vec, rho_co2_vec, rho_h2o_vec = get_pvt()

    #Make interpolators for the imported tables
    get_rho_h2o = RectBivariateSpline(p_vec, t_vec, rho_h2o_vec)

    #Make the depth-vector from msl and downwards
    td_msl = well_header['well_td_rkb']-well_header['well_rkb']
    z_vec  = np.arange(0, int(td_msl)+2, dz)

    #Create dataframe for storing pressures and temperatures. hs_p_df -> HydroStatic_Pressure_DataFrane
    hs_p_df = pd.DataFrame(data=z_vec, columns = ['depth_msl'])

    #Compute temperature. Constant in water column and as a function of input geothermal gradient
    hs_p_df['temp'] = well_header['sf_temp'] + (hs_p_df['depth_msl']-well_header['sf_depth_msl'])*(well_header['geo_tgrad']/1000)
    hs_p_df.loc[hs_p_df['depth_msl']<well_header['sf_depth_msl'], 'temp'] = well_header['sf_temp']


    ##Integrate hydrostatic pressure
    #Pressure (atm), depth and temperature at msl
    p0 = scipy.constants.atm/scipy.constants.bar  #1.01325 bar Pressure at MSL
    z0 = 0
    t0 = np.interp(z0, hs_p_df['depth_msl'], hs_p_df['temp'])

    #Start to integrate downwards from msl. Assign first entry at zero depth (msl).
    rho_vec = [get_rho_h2o(p0, t0)[0,0]]
    hs_p_df['hs_p'] = p0 

    p = p0
    for idx, t in hs_p_df['temp'][1:].items():
        rho = get_rho_h2o(p,t)[0,0]
        p += (rho*G*dz)/scipy.constants.bar    #dp = rho*g*h/1e-5  the latter to go from Pascal to atm
        rho_vec.append(rho)
        hs_p_df.loc[idx, 'hs_p'] = p
    hs_p_df['RHOH2O'] = rho_vec

    return hs_p_df


def fraction_float(frac_str):
    ''' Evaluates numbers as e.g. 12 1/4 '''
    frac_str = frac_str.split()    # "12"  "1/4"
    integer = frac_str[0]          # "12"
    rational = eval(integer)       # 12
    if len(frac_str)>1:
        fraction = frac_str[1]     #1/4
        rational += eval(fraction) #12 + 0.25
    return rational


def float_to_fraction_inches(d_in):
        """Converts float number to integer fraction string"""
        int_d = int(d_in)                                          #int(12.25) = 12
        remainder = d_in - int_d                                   #0.25
        if remainder > 0:
                fraction = remainder.as_integer_ratio()            #0.25 -> 1/4 ->  (1, 4)
                fraction_str = f'{fraction[0]}/{fraction[1]}'      #"1/4"
                d_fmt = f'{int_d} {fraction_str}"'                 #"12 1/4"  
                return d_fmt
        else:
                d_fmt = f'{int_d}"'                                #"12"
                return d_fmt


def csv_parser(csv_file):
    with open(csv_file, encoding='utf-8-sig') as f:
        lines = f.read()
    lines = re.sub('\,+\n', '\n', lines)

    well = dict()
    for section in lines.split('\n\n'):
        sec_lines = section.strip().split('\n')
       
        if len(sec_lines)>1:
            table_title = sec_lines[0]
            table_str   = '\n'.join(sec_lines[1:])

            if table_title.lower() == 'well_header':
                table = pd.read_csv(io.StringIO(table_str), names=['attribute', 'value'], header=None, index_col=0, usecols=[0,1]).squeeze()
                for attribute, value in table.items():
                    try:
                        table[attribute] = float(value)
                    except:
                        table[attribute] = value

            elif table_title.lower() == 'reservoir_pressure':
                table = pd.read_csv(io.StringIO(table_str), index_col=False).squeeze()
                #print(table)

            elif table_title.lower() == 'barrier_permability':
               table = pd.read_csv(io.StringIO(table_str), index_col=False).squeeze()

            elif table_title.lower() in ['main_barrier', 'co2_datum']:        
                table = pd.read_csv(io.StringIO(table_str), header= None, index_col=0).squeeze()

            else:
                table = pd.read_csv(io.StringIO(table_str))
                if table_title in ['drilling', 'casing_cement']:
                    table['diameter_in'] = table['diameter_in'].map(fraction_float)
            try:
                well[table_title] = table.to_dict()
                # well[table_title] = table
            except:
                well[table_title] = table            
    return well


@dataclass
class Well:
    header        : dict = None
    reservoir_P   : dict = None
    drilling      : dict = None
    casings       : dict = None
    barriers      : dict = None
    geology       : dict = None
    borehole      : dict = None
    barriers_mod  : dict = None
    cement_bond   : dict = None
    main_barrier  : dict = None
    barrier_perm  : dict = None 
    co2_datum     : dict = None

    
    def __post_init__(self):
        self.process_drilling()
        self.process_casings()
        self.process_barriers()
        self.compute_borehole()
        self.compute_barriers_diam()
        self.compute_cement_bond()
        self.check_init_pressure()
        self.process_geology()
        self.get_barrier_properties()

    def process_drilling(self):
        drilling_df = pd.DataFrame(self.drilling)
        drilling_df['diameter_m'] = drilling_df['diameter_in'] * scipy.constants.inch       #0.0254
        drilling_df['top_msl']    = drilling_df['top_rkb'] - self.header['well_rkb']
        drilling_df['bottom_msl'] = drilling_df['bottom_rkb'] - self.header['well_rkb']
        self.drilling = drilling_df.to_dict()

    def process_casings(self):
        casings_df = pd.DataFrame(self.casings)
        casings_df['diameter_m'] = casings_df['diameter_in'] * scipy.constants.inch         #0.0254
        casings_df['top_msl']    = casings_df['top_rkb']    - self.header['well_rkb']
        casings_df['bottom_msl'] = casings_df['bottom_rkb'] - self.header['well_rkb']
        casings_df['toc_msl']    = casings_df['toc_rkb']    - self.header['well_rkb']
        casings_df['boc_msl']    = casings_df['boc_rkb']    - self.header['well_rkb']
        self.casings = casings_df.to_dict()

    def process_barriers(self):
        barriers_df = pd.DataFrame(self.barriers)
        barriers_df['top_msl']    = barriers_df['top_rkb']    - self.header['well_rkb']
        barriers_df['bottom_msl'] = barriers_df['bottom_rkb'] - self.header['well_rkb']
        # barriers_df.set_index('barrier_name', inplace=True)
        self.barriers = barriers_df.to_dict()
    
    def process_geology(self):
        geology_df = pd.DataFrame(self.geology)
        geology_df = geology_df.dropna(how='all')
        geology_df = geology_df.reset_index(drop=True)

        geology_df['top_msl']  = geology_df['top_rkb'] - self.header['well_rkb']
        geology_df['base_msl'] = geology_df['top_msl'] - geology_df['top_msl'].diff(periods=-1)
        geology_df.loc[geology_df.index.max(), 'base_msl'] = self.header['well_td_rkb'] - self.header['well_rkb']

        self.geology = geology_df.to_dict()


    
    def compute_borehole(self):
        '''
        Routine to compute the effective open borehole. 
        It takes the original hole and substracts the diameter taken by cement bond.
        '''
        casings_df  = pd.DataFrame(self.casings)
        drilling_df = pd.DataFrame(self.drilling)

        well_concat = pd.concat([casings_df, drilling_df])
        top_z = well_concat['top_msl'].drop_duplicates().dropna().values
        top_z.sort()

        diam = 1 + well_concat['diameter_m'].max()

        borehole = []
        for z_value in top_z:
            z_query = well_concat.query('top_msl == @z_value')
            min_q = z_query.query('diameter_m == diameter_m.min()')
            if min_q.iloc[0]['diameter_m'] < diam:
                borehole.append(min_q.iloc[0][['top_msl', 'bottom_msl', 'diameter_m']].values.tolist())
                diam = min_q.iloc[0]['diameter_m']

        borehole = np.array(borehole)
        # borehole[:-1, 1] = borehole[1:, 0]
        borehole[1:, 0] = borehole[:-1, 1]

        borehole_df = pd.DataFrame(data=borehole, columns=['top_msl', 'bottom_msl', 'id_m'])
        self.borehole = borehole_df.to_dict()

    
    def compute_barriers_diam(self):
        '''
        Processes barriers data. Takes the cumputed borehole data to recompute 
        the barrier intervals in cases where the barriers are sitting along differen hole sizes
        '''

        barriers_fmt = defaultdict(lambda: defaultdict())
        barriers_df = pd.DataFrame(self.barriers)
        borehole_df = pd.DataFrame(self.borehole)

        for idx, row in barriers_df.iterrows():
            barr_idx = idx
            barrier = row[0]
            b_type = row[1]
            top = row['top_msl']
            bottom = row['bottom_msl']

            check_top_int_top = top >= borehole_df['top_msl']
            check_bottom_int_top = top < borehole_df['bottom_msl']

            check_top_int_bottom = bottom > borehole_df['top_msl']
            check_bottom_int_bottom = bottom < borehole_df['bottom_msl']

            barrier_topD = borehole_df[check_top_int_top & check_bottom_int_top]['id_m'].iloc[0]
            barrier_bottomD = borehole_df[check_top_int_bottom & check_bottom_int_bottom]['id_m'].iloc[0]

            if barrier_topD == barrier_bottomD:
                barrier_name = '{:s}_{:d}'.format(barrier, barr_idx)
                barriers_fmt[barrier_name]['b_name'] = barrier
                barriers_fmt[barrier_name]['top_msl'] = top
                barriers_fmt[barrier_name]['bottom_msl'] = bottom
                barriers_fmt[barrier_name]['diameter_m'] = barrier_topD
            else:
                barrier_query = borehole_df.query('id_m <= @barrier_topD and id_m >= @barrier_bottomD')
                for idx, sub_section in barrier_query.iterrows():
                    barrier_name = '{:s}_{:d}'.format(barrier, barr_idx)
                    barriers_fmt[barrier_name]['b_name'] = barrier

                    barriers_fmt[barrier_name]['top_msl'] = max(sub_section['top_msl'], top)
                    barriers_fmt[barrier_name]['bottom_msl'] = min(sub_section['bottom_msl'], bottom)
                    barriers_fmt[barrier_name]['diameter_m'] = sub_section['id_m']
                    barr_idx += 1

        barriers_fmt_df = pd.DataFrame(barriers_fmt).T
        self.barriers_mod = barriers_fmt_df.to_dict()

    def compute_cement_bond(self):
        '''
        Processes cement bond intervals. Reads both casing and borehole sizes to estimate cement bond width
        '''
        cb_fields = []

        casings_df = pd.DataFrame(self.casings)
        drilling_df = pd.DataFrame(self.drilling)

        for idx, row in casings_df[::-1].iterrows():
            d, top, bottom = row[['diameter_m', 'toc_msl', 'boc_msl']]

            hole = drilling_df[drilling_df['diameter_m'] > d].iloc[-1]
            hole_top, hole_bottom, hole_d = hole[['top_msl', 'bottom_msl', 'diameter_m']]

            if top >= hole_top and bottom <= hole_bottom:
                cb_fields.append((top, bottom, d, hole_d))
            else:
                bond_query = casings_df.query('diameter_m > @d & bottom_msl > @top')
                bond_query = bond_query.sort_values(by='diameter_m')
                temp_top_cb = bond_query['bottom_msl'].max()
                cb_fields.append((temp_top_cb, bottom, d, hole_d))

                for idx, row in bond_query.iterrows():
                    if row['top_msl'] <= top:
                        section_top = top
                        section_bottom = temp_top_cb
                        cb_fields.append((section_top, section_bottom, d, row['diameter_m']))
                        break
                    else:
                        section_top = row['top_msl']
                        section_bottom = temp_top_cb
                        cb_fields.append((section_top, section_bottom, d, row['diameter_m']))
                        temp_top_cb = row['top_msl']

        cement_bond_df = pd.DataFrame(data=cb_fields, columns=['top_msl', 'bottom_msl', 'id_m', 'od_m'])
        self.cement_bond = cement_bond_df.to_dict()

    def check_init_pressure(self):
        '''
        Calculates hydrostatic pressure at 
        reservoir_P is the entry looking something like this:

        reservoir_pressure		
        depth_msl	RP1	RP2
        2238		        20

        then P_init['depth_msl'] is the reference depth 2238

        Also delta-pressures RP1 and RP2 are read and used later for leakage calculations. (self.reservoir_P[])

        Note: The interpretation of the numbers set for RP1 and RP2 is a bit unclear. RP means reservoir pressure - but for the current
              implementation it is interpreted as delta pressure: delta wrt hydrostatic pressure. 
              Initial implementation had the possibility to have absolute pressure AND a delta-pressure. But the delta-pressure had to be 
              given as a string "+ 20" or "- 15". Bit the + and - tended to create problems. 
              So alternatively one could distingwuish between RP and DP  if it is important to give in absolute pressure as well.
              But the most interesting input IS actually the change in pressure compared with hydrostatic pressure.

        '''
        P_init = self.reservoir_P

        #Get hydrostatic pressure
        ref_z        = P_init['depth_msl']                                                  #A reference depth given in the input, e.g. top reservoir
        hydrostaticP = get_hydrostatic_P(self.header)                                       #Calculate depth, temp(depth) hydrostatic_pressure(depth), H2ORHO(depth for hydrostatic pressure)
        ref_p        = np.interp(ref_z, hydrostaticP['depth_msl'], hydrostaticP['hs_p'])    #Hydrostatic pressure at that depth
        print(f"Hydrostatic pressure at reference depth {ref_z:.0f} is {ref_p:.2f}")

        self.reservoir_P['hydrostatic_pressure'] = ref_p

        for key in P_init.copy():   #Should just loop the RPs and check for isnan for each instead of special treatment of RP1. Call it DP1 DP2 instead. Delta Pressure
            if key == 'RP1':
                RP1 = P_init[key]
                if np.isnan(RP1):
                    print(f'RP1 set as hydrostatic P = {ref_p:.2f} bar')
                    self.reservoir_P['RP1'] = ref_p
                else:
                    print(f'RP1 is set as delta pressure, which yields P = {ref_p:.2f} {RP1:+.2f} = {ref_p + RP1:.2f} bar')
                    self.reservoir_P['RP1'] = ref_p + RP1
            elif key.startswith('RP'):
                RP = P_init[key]
                try:
                    if isinstance(RP, str):
                        RP = RP.replace(" ", "")
                    RP = float(RP)
                except:
                    pass
                if isinstance(RP, float) or isinstance(RP, int):
                    p = ref_p + RP                          #self.reservoir_P['RP1'] + RP
                    print(f'{key} is set as delta pressure, which yields P = {ref_p:.2f} {RP:+.2f} = {ref_p + RP:.2f} bar')
                    self.reservoir_P[key] = ref_p + RP
                else:
                    P_init.pop(key)
                    print(RP, 'ignored')
                    continue    
                
    def _compute_CO2_pressures(self):
        '''The pressure and density for H2O and CO2  along the columns are calculated using an approximate integration
           Hydrostatic pressure - caculatong downwards from msl
           Pressure and density assuming a water column - starting at top reservoir and the given overpressure RP
           Pressure and density assuming a CO2   column - starting at CO2-reference level (CO2-column could start below top reservoir) and the given overpressure RP
           Shmin

           Columns are
              depth_msl        temp          hs_p         RHOH20            Shmin   RPx_h20        RPx_h20_rho     RPx_co2                            RPx_co2_rho     RPx_h2o_rho_in_co2_column
             depth below msl   temperature   hydrostatic  water density             hs_p+          densities at    Pressure given a CO2 column        Corresponding   water densitites if we are
             depth ref for                   pressure     at hydrostatic            overpressure   RPx_h20         and overpressure RP                CO2 densities   in a CO2-column.
             all other values                column       pressure                  RPx
           
           

            ---> The RP are all RP-input + hydrostatic_pressure. Hence if e.g. RP1 is hydrostatic pressure RP1-columns and hydrostatic_pressure-columns are identical.
        '''
        well_header = self.header
        p_init      = self.reservoir_P
        base_co2    = self.co2_datum

        t_vec, p_vec, rho_co2_vec, rho_h2o_vec = get_pvt()
        p_msl = scipy.constants.atm/scipy.constants.bar  #1.01325 bar Pressure at MSL

        get_rho_h2o = RectBivariateSpline(p_vec, t_vec, rho_h2o_vec)
        get_rho_co2 = RectBivariateSpline(p_vec, t_vec, rho_co2_vec)

        def get_rho(phase, p, t):
            if phase=='co2':
                rho  = get_rho_co2(p,t)[0, 0]
            elif phase == 'h2o':
                rho  = get_rho_h2o(p,t)[0, 0]


        #Get hydrostatic pressure from msl and downwards
        pt_df = get_hydrostatic_P(self.header)                     #Calculate depth, temp(depth) hydrostatic_pressure(depth), H2ORHO(depth for hydrostatic pressure)

        #Compute Shmin
        wd = well_header['sf_depth_msl']                           #Depth to sea floor
        wp_ml = np.interp(wd, pt_df['depth_msl'], pt_df['hs_p'])   #Pressure at sea floor
        pt_df['Shmin'] = pt_df['hs_p']                             #Initialize with hydrostatic pressure
        shmin_query = pt_df.query('depth_msl>=@wd')                #Take only values below sea floor
        pt_df.loc[pt_df['depth_msl']>=wd, 'Shmin'] = wp_ml + (shmin_query['depth_msl']-wd)*0.1695

        #Find hydrostatic pressure and temperature at reference depth - typically at top reservoir
        ref_z = p_init['depth_msl']
        ref_z_hsp = np.interp(ref_z, pt_df['depth_msl'], pt_df['hs_p'])
        ref_z_temp = np.interp(ref_z, pt_df['depth_msl'], pt_df['temp'])

        #Integrate from reference depth and upwards given different starting pressures
        for key, value in p_init.items():                 #depth_msl, RP1, RP2, hydrostatic_pressure
            if key == 'depth_msl':                        #No calculations - just report
                print(f"Reference depth: {value}")
            else:
                phases_zval = [('h2o', ref_z), ('co2', base_co2)]
                rp = key                                  #pressure name
                p0 = value                                #initial pressure value

                for phase, ref_depth in phases_zval:
                        #crate column names in dataframe
                        colname_p   = rp+'_'+phase
                        colname_rho = rp+'_'+phase+'_rho'

                        #create empty columns for each phase
                        pt_df[colname_p] = np.nan         #pressure
                        pt_df[colname_rho] = np.nan       #density

                        #Assign pressure-value at reference point if depth value exists
                        pt_df.loc[pt_df.depth_msl == ref_depth, colname_p] = p0
                        
                        #Create tuple lists for sections for integration
                        segments_list = []

                        #Split vector in two sections for iterations: upwards(-1) and downwards(+1)
                        above_ref_query = pt_df.query('depth_msl<=@ref_depth')
                        segments_list.append((above_ref_query, -1))
                        
                        #below segment only evaluated for water
                        if phase == 'h2o':
                                below_ref_query = pt_df.query('depth_msl>@ref_depth')
                                segments_list.append((below_ref_query, 1))

                        #if CO2 - then p0 is updated to H2O pressure at CO2 datum
                        if phase == 'co2':
                                p0 = np.interp(ref_depth, pt_df['depth_msl'], pt_df[rp+'_h2o'])
                                #Update pressure-value at reference point if depth value exists (is it really needed?)
                                pt_df.loc[pt_df.depth_msl == ref_depth, colname_p] = p0

                        #interpolate temperature to given value
                        t0 = np.interp(ref_z, pt_df['depth_msl'], pt_df['temp'])

                        #Update temperature-value and density-value at reference point if depth value exists (is it really needed?)
                        pt_df.loc[pt_df.depth_msl == ref_depth, colname_rho] = get_rho(phase, p0, t0)
                        pt_df.loc[pt_df.depth_msl == ref_depth, colname_p]   = p0

                        for segment, sign in segments_list:
                                p  = p0
                                z0 = ref_depth

                                for z_idx, row in segment[::sign].iterrows():
                                        t = row['temp']
                                        z = row['depth_msl']

                                        if phase == 'h2o':
                                                rho = get_rho_h2o(p, t)[0,0]
                                        else:
                                                rho = get_rho_co2(p, t)[0,0]

                                        dz = z - z0
                                        p += (rho*G*dz)/scipy.constants.bar    #1e-5
                                        if p<p_msl:
                                                p=p_msl
                                        
                                        pt_df.loc[z_idx, colname_p] = p
                                        pt_df.loc[z_idx, colname_rho] = rho
                                        z0 = z

                #We need the density for water given the CO2-pressures, too
                temps = pt_df['temp']
                pressures = pt_df[f'{rp}_co2']
                rhos = []
                for t, p in zip(temps, pressures):
                    rhos.append(get_rho_h2o(p,t)[0,0])

                pt_df[f"{rp}_h2o_rho_in_co2_column"] = rhos[:]

        #pt_df.to_csv("pt.csv")
        self.pressure_CO2 = pt_df
        
    def plot_sketch(self, ax=None):
        if ax is None:
             fig, ax = plt.subplots()
             

        drilling_df =     pd.DataFrame(self.drilling)
        casings_df =      pd.DataFrame(self.casings)
        cb_df =           pd.DataFrame(self.cement_bond)
        borehole_df =     pd.DataFrame(self.borehole)
        barriers_df =     pd.DataFrame(self.barriers)
        barriers_fmt_df = pd.DataFrame(self.barriers_mod)
        geology_df =      pd.DataFrame(self.geology)
        well_header =     self.header



        #define plot spatial references
        ax_width = 2 * drilling_df['diameter_m'].max()/2 #plot width
        xcoord_left = -drilling_df['diameter_m'].max()/2 #well construction text
        xcoord_right = drilling_df['diameter_m'].max()/2 #geology text
        txt_fs_left = 7
        txt_fs_right = 6
        steelcolor = '#702F00'
        base_deepest_rsrv = geology_df[geology_df.reservoir_flag]['base_msl'].max()
        ymax = max([base_deepest_rsrv,self.co2_datum])+100
        

        # Draw drilling (Bit size)
        for idx, row in drilling_df.iterrows():
             xy = (-row['diameter_m']/2, row['top_msl'])
             width = row['diameter_m']
             height = row['bottom_msl'] - row['top_msl']
             ax.add_patch(Rectangle(xy, width, height, zorder=0, facecolor=r'#CB8A58'))

        #Draw casings
        ax.vlines(x= casings_df['diameter_m']/2, ymin=casings_df['top_msl'], ymax=casings_df['bottom_msl'],  color=steelcolor, lw=1.5, zorder=10)
        ax.vlines(x=-casings_df['diameter_m']/2, ymin=casings_df['top_msl'], ymax=casings_df['bottom_msl'],  color=steelcolor, lw=1.5, zorder=10)

        #Draw casing shoes
        shoe_size = 3

        left_shoe = [[0, 0], [-shoe_size, 0], [0, shoe_size], [0, 0]]
        right_shoe = [[0, 0], [shoe_size, 0], [0, shoe_size], [0, 0]]

        shoe_query = casings_df[casings_df['shoe']]

        ax.scatter( shoe_query['diameter_m']/2, shoe_query['bottom_msl'], marker = right_shoe, c=steelcolor, zorder=10)
        ax.scatter(-shoe_query['diameter_m']/2, shoe_query['bottom_msl'], marker = left_shoe, c=steelcolor, zorder=10)

        for idx, row in shoe_query.iterrows():
                ycoord = row['bottom_msl']
                d_in = row['diameter_in']
                shoe_label = float_to_fraction_inches(d_in)+' shoe'
                ax.annotate(shoe_label, xy = (xcoord_left, ycoord), fontsize = txt_fs_left, va = 'center', ha='right')

        #Draw welded 
        weld_query = casings_df[~casings_df['shoe'].astype(bool)]

        for idx, row in weld_query.iterrows():
                max_D = row['diameter_m']
                max_Z = row['bottom_msl']

                query = casings_df.query('diameter_m<@max_D & top_msl==@max_Z')
                min_D = query.iloc[0]['diameter_m']

                ax.plot([ max_D/2,  min_D/2], [max_Z]*2, c=steelcolor, zorder=10)
                ax.plot([-max_D/2, -min_D/2], [max_Z]*2, c=steelcolor, zorder=10)

        #Draw cement bond
        for idx, row in cb_df.iterrows():
                width = (row['od_m'] - row['id_m'])/2
                height = row['bottom_msl'] - row['top_msl']

                right_xy = (row['id_m']/2, row['top_msl'])
                left_xy = (-row['od_m']/2, row['top_msl'])

                ax.add_patch(Rectangle(right_xy, width, height, facecolor='lightgray', zorder=5, hatch='\\\\\\'))
                ax.add_patch(Rectangle(left_xy, width, height, facecolor='lightgray', zorder=5 , hatch='///'))

        #draw barriers
        for idx, row in barriers_fmt_df.iterrows():

                xy = (-row['diameter_m']/2, row['top_msl'])
                width = row['diameter_m']
                height = row['bottom_msl'] - row['top_msl']
                ax.add_patch(Rectangle(xy, width, height, facecolor='gray', zorder=1))

        for idx, row in barriers_df.iterrows():
                ycoord = (row['top_msl'] + row['bottom_msl'])/2
                ax.annotate(text = row['barrier_name'], xy = (xcoord_left, ycoord), fontsize = txt_fs_left, va = 'center', ha='right')

        # Draw open hole (borehole/pipe) for testing only
        # for idx, row in borehole_df.iterrows():
        #      xy = (-row['id_m']/2, row['top_msl'])
        #      width = row['id_m']
        #      height = row['bottom_msl'] - row['top_msl']
        #      ax.add_patch(Rectangle(xy, width, height, zorder=9, fill=False, edgecolor='k', lw=2, ))


        #Draw geological information
        ax.hlines(y=geology_df['top_msl'], xmin=-ax_width, xmax=ax_width, zorder=-4, lw=.25, color='k')
        ax.axhspan(0, well_header['sf_depth_msl'], color='lightblue', alpha=0.5, zorder=-20)
        ax.axhspan(well_header['sf_depth_msl'], well_header['well_td_rkb'], color='tan', alpha=0.5, zorder=-20)

        
        for index, row in geology_df.iterrows():
            if row['reservoir_flag']:
                ax.axhspan(row['top_msl'], row['base_msl'], color='yellow', zorder=-10)
        
            ycoord = (row['top_msl'] + row['base_msl'])/2
            ax.annotate(text = row['geol_unit'], xy = (xcoord_right, ycoord), fontsize = txt_fs_right, va = 'center')




        ax.set_xlim(-ax_width, ax_width)
        ax.set_ylim(0, ymax)
        ax.invert_yaxis()
        ax.set_ylabel('depth [mMSL]')
        ax.set_xlabel('radius [m]')
        
        if 'fig' in locals():
             return fig, ax
        else:
             return ax
    
    def plot_pressure(self, ax = None):
        if ax is None:
             fig, ax = plt.subplots()
         
        if not hasattr(self, "pressure_CO2"):
            self._compute_CO2_pressures()
        pt_df = self.pressure_CO2

        well_header = self.header
        sf_depth    = well_header['sf_depth_msl']
        barriers_df = pd.DataFrame(self.barriers)
        geology_df  = pd.DataFrame(self.geology)
        
        #define plot spatial references
        base_deepest_rsrv = geology_df[geology_df.reservoir_flag]['base_msl'].max()
        ymax = max([base_deepest_rsrv,self.co2_datum])+100
        xmax = pt_df.query('depth_msl>@ymax')['Shmin'].iloc[0]
        xmin = 0
        
        # Draw cement plugs
        for idx, row in barriers_df.iterrows():
            barrier = ax.axhspan(row['top_msl'], row['bottom_msl'], color='lightgray', zorder=-20, label = 'cement plug')

        #Plot hydrostatic pressure gradient
        pt_df.plot(x='hs_p', y='depth_msl', ax=ax, label='$p_{hs}$', color='steelblue', lw = 0.75)

        #Plot minimum horizontal stress
        pt_df.plot(x='Shmin', y='depth_msl', ax=ax, label='$\sigma_{h min}$', color='k', lw = 0.75)

        #Plot fluid pressure scenarios
        ls_list = ['solid','dashed','dashdot', 'dotted']
        counter = 0

        for key in self.reservoir_P:
                if key != 'depth_msl':
                        pt_df.query('depth_msl>=@sf_depth').plot(x=key+'_h2o', y='depth_msl', ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])
                        pt_df.query('depth_msl>=@sf_depth').plot(x=key+'_co2', y='depth_msl', ax=ax, label = key, color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])

                        counter+=1
                        counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter                        
        
        #Optimize legend
        ax.legend()
        handles, labels = ax.get_legend_handles_labels()  
        lgd = dict(zip(labels, handles))
        ax.legend(lgd.values(), lgd.keys())
        
        ax.set_xlim(xmin, xmax)
        ax.set_xlabel('presure [bar]')
        ax.set_ylim(0, ymax)
        ax.invert_yaxis()
        if 'fig' in locals():
             return fig, ax
        else:
             return ax
        
    def plot_pt(self, fig=None, ax=None):

        if fig == None:
            fig, ax = plt.subplots()


        t, p, rho_co2, rho_h2o = get_pvt()

        #Plot density colormap
        rho_pcm = ax.pcolormesh(t, p, rho_co2, alpha=0.5)

        #Plot phase boundary and critical point
        t_co2 = np.array([-50,-48.35,-46.69,-45.04,-43.38,-41.73,-40.08,-38.42,-36.77,-35.11,-33.46,-31.81,-30.15,-28.5,-26.84,-25.19,-23.53,-21.88,-20.23,-18.57,-16.92,-15.26,-13.61,-11.96,-10.3,-8.65,-6.99,-5.34,-3.69,-2.03,-0.38,1.28,2.93,4.58,6.24,7.89,9.55,11.2,12.86,14.51,16.16,17.82,19.47,21.13,22.78,24.43,31.05])
        p_co2 = np.array([6.8,7.27,7.77,8.29,8.83,9.4,10,10.63,11.28,11.97,12.68,13.43,14.21,15.02,15.87,16.75,17.66,18.62,19.61,20.64,21.7,22.81,23.96,25.15,26.38,27.66,28.98,30.34,31.76,33.21,34.72,36.28,37.89,39.54,41.25,43.01,44.83,46.7,48.63,50.61,52.65,54.75,56.91,59.12,61.4,63.75,73.76])
        ax.plot(t_co2, p_co2, color='k', lw=1.5, label = r'$CO_2$ phase env.')
        ax.scatter(t_co2.max(), p_co2.max(), c='k')

        #Retrieve pressures as well
        if not hasattr(self, "pressure_CO2"):
            self._compute_CO2_pressures()
        pt_df = self.pressure_CO2

        wd = self.header['sf_depth_msl']
        co2_datum = self.co2_datum

        #Plot fluid pressure scenarios
        ls_list = ['solid','dashed','dashdot', 'dotted']
        counter = 0

        ymax = 0
        for key in self.reservoir_P:
                if key != 'depth_msl':
                        pt_df.query('depth_msl>=@wd').plot(y=key+'_h2o', x='temp', ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])
                        pt_df.query('depth_msl>=@wd').plot(y=key+'_co2', x='temp', ax=ax, label = f'$CO_2$ {key}', color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])
                        
                        base_msl = pt_df.query('depth_msl>(@co2_datum)+50')[key+'_h2o'].iloc[0]

                        if base_msl > ymax:
                                ymax = base_msl

                        counter+=1
                        counter = counter%(len(ls_list))  #If more cases than in ls_list then restart counter

        xmax = pt_df.query('depth_msl>(@co2_datum)+50')['temp'].iloc[0]

        ax.set_ylabel('p [bar]')
        ax.set_xlabel('T [$\degree$C]')
        ax.set_xlim(1, xmax)
        ax.set_ylim(1, ymax)
        fig.colorbar(rho_pcm, label=r'$\rho_{CO_2}$ [$kg/m^3$]')

        fig.tight_layout()
        plt.show()

    def _get_barriers_names(self):
        '''Each barrier is divided into sections with constand diameter. Most barriers do of course have only one section, but in the preprocessing
           the barrier diameter is calculated based on casing etc and not given explicitely. Also top and base is divided into these sections in the class object.
           Original format:   barr1_0: barr1, barr1_1: barr1, barr2_0: barr2    where barr1 here is divided into the two sections barr1_0 and barr1_1
           New format         barr1: [barr1_0, barr1_1], barr2: [barr2_0]'''
        names = self.barriers_mod["b_name"]
        bnames = {key: [j for j, _ in list(value)] for key, value in groupby(names.items(), lambda x: x[1])}
        self.barriers_names = bnames

    def _get_barrier_height_and_depth(self, barrier_name):
        '''Get height (m) top (msl) nd bottom (msl) of the barrier   barrier_name.
           As it is now only the main barrier is used as input, but the code here
           is general so one might e.g. loop over all barriers if needed
        '''
        top    = []
        bottom = []
        for bname in self.barriers_names[barrier_name]:                       #Loop over the sections of this barrier
            top.append(self.barriers_mod['top_msl'][bname])
            bottom.append(self.barriers_mod['bottom_msl'][bname])

        #Initiate barrier_name in barrier_props if needed. 
        if barrier_name not in self.barrier_props:
            self.barrier_props[barrier_name] = {}

        self.barrier_props[barrier_name]['height'] = max(bottom) - min(top)
        self.barrier_props[barrier_name]['top']    = min(top)
        self.barrier_props[barrier_name]['bottom'] = max(bottom)

    def _get_barrier_radius(self, barrier_name):
        '''Height-averaged radius if the barrier varies in diameter'''
        heights = []
        diams   = []
        avg_diam = 0

        #Collect diameters and heights
        for bname in self.barriers_names[barrier_name]:
            heights.append(self.barriers_mod['bottom_msl'][bname] - self.barriers_mod['top_msl'][bname])
            diams.append(self.barriers_mod['diameter_m'][bname])
            
        #Do the avaraging
        for diam, height in zip(diams, heights):
            avg_diam += diam*height
        avg_diam /= sum(heights)

        self.barrier_props[barrier_name]['radius'] = avg_diam/2.0
                           
    def _get_barrier_p_and_rho(self, barrier_name):
        ''' Calculates pressure above and below the barrier 
            and densities below the barrier using the assumption 
            that the borehole is filled with water above the barrier 
            and filled with CO2 below the barrier
        '''

        #Get the pressure cases to include
        rp_names = []
        for key in self.reservoir_P:
            if key.startswith("RP"):
                rp_names.append(key)

        df = pd.DataFrame(columns=["p_h2o_above_barrier", "p_co2_below_barrier", "rho_h2o_below_barrier", "rho_co2_below_barrier"], index=rp_names)
        depth = self.pressure_CO2["depth_msl"]           #Depth look up table used in the interpolation of pressure and densities in the self.pressure_CO2 dataframe.
        top   = self.barrier_props[barrier_name]['top']
        bottom= self.barrier_props[barrier_name]['bottom']
   
        df["p_h2o_above_barrier"] = [np.interp(top,    depth, self.pressure_CO2["hydrostatic_pressure_h2o"])]*len(rp_names)
        df["p_co2_below_barrier"] = [np.interp(bottom, depth, self.pressure_CO2[f"{key}_co2"]) for key in rp_names]

        df["rho_h2o_below_barrier"]  = [np.interp(bottom, depth, self.pressure_CO2[f"{key}_h2o_rho_in_co2_column"]) for key in rp_names]
        df["rho_co2_below_barrier"]  = [np.interp(bottom, depth, self.pressure_CO2[f"{key}_co2_rho"]) for key in rp_names]

        self.barrier_props[barrier_name]['p_and_rho'] = df.copy()


    def get_barrier_properties(self):
        ''' Collect all the properties of the barrier needed and calculate the rate proxy.
            As now only the main barrier is used, but it should be easy to generalize to all barriers
            in e.g. a loop if needed 

            self.barrier_props contains all info needed abour a barrier such as dimensions, depth, pressures and densities above and below, potential leakage rates
            Note that barrier permeability is already avilable through self.barrier_perm and is hence not duplicated'''

        if not hasattr(self, "pressure_CO2"):
            self._compute_CO2_pressures()

        self.barrier_props = {} #All subsequent results are put into self.barrier_props[barrier_name] for a given barrier.
        self._get_barriers_names()
        self._get_barrier_height_and_depth(self.main_barrier)
        self._get_barrier_radius(self.main_barrier)
        self._get_barrier_p_and_rho(self.main_barrier)
        self._get_barrier_leakage(self.main_barrier)
        

    def _get_barrier_leakage(self, barrier_name):
        ''' Returns an estimate of CO2 leakage in [tons/day] after a trancient period.
            It also is based on than the reservoir pressur does not change - hence if the process is completely stationary except for the leakage, 
            i.e. the leaked volumes are << than the reservoir volumes.
            The proxy is based on two steps:
            proxy1: r*r*k/l*(g*drho*l + dp*10**5)    -> To get the most important physical properties determining rate
            proxy2: a + b*proxy1                     -> To calibrate to actual rates estimated by a large number of runs done in pflotran.

           The variables in the proxy regression must come from somewhere.
           Here it is hardcoded in the header, but one could imagine to have several models fit for different circumstances.
           Then the parameteters could be case dependent and an input
        '''

        #Get the permeabilty values to use
        perms = self.barrier_perm['kv'].values()

        #Get the pressure cases to use (RP1, RP2 etc)
        cases = self.barrier_props[barrier_name]['p_and_rho'].index

        #Make data-structurs ready.
        df_leakage = pd.DataFrame(columns=perms, index = cases)
        df_p_rho = self.barrier_props[barrier_name]['p_and_rho'].copy()

        #To make the formula below easier to read
        r      = self.barrier_props[barrier_name]['radius']
        length = float(self.barrier_props[barrier_name]['height'])

        for k in perms:                                                         #Loop the permeability-cases
            for case in cases:                                                  #Loop the pressure cases
                drho = df_p_rho.loc[case, 'rho_h2o_below_barrier'] - df_p_rho.loc[case, 'rho_co2_below_barrier']
                dp   = df_p_rho.loc[case, 'p_co2_below_barrier']   - df_p_rho.loc[case, 'p_h2o_above_barrier']

                prox = (r*r*k/length)*(G*length*drho + dp*BAR2PA)
                df_leakage.loc[case,k] = np.round(max(REGR_A + REGR_B*prox,0),5)
        
        print(df_leakage)
        self.barrier_props[barrier_name]['leakage'] = df_leakage.copy()

    @property
    def to_json(self):
        return json.dumps(self.__dict__, indent=4)
