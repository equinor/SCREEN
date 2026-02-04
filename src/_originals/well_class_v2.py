import pandas as pd
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
import json
import re
import io
from scipy.interpolate import RectBivariateSpline
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def parse_spreadsheet(filename):
    wbook_df = pd.read_excel(filename, header=None, sheet_name=None)



    wsheet_names = list(wbook_df.keys())
    print(f'Reading spreadsheet with {len(wsheet_names)} worksheet(s): {", ".join(wsheet_names)}')

    ip_data = wbook_df[wsheet_names[0]]

    if len(wsheet_names)>1:
        ip_init = wbook_df[wsheet_names[1]]
    else:
        print('No initialization pmts defined')


    #Map indexes of spreadsheet rows
    drilling_idx =     ip_data[ip_data.isin(['Drilling']).any(axis=1)].index[0]
    casing_idx =       ip_data[ip_data.isin(['Casing and cement bond']).any(axis=1)].index[0]
    barriers_idx =     ip_data[ip_data.isin(['Barriers']).any(axis=1)].index[0]
    geology_idx =      ip_data[ip_data.isin(['Geology']).any(axis=1)].index[0]
    resrv_P_idx =      ip_init[ip_init.isin(['Reservoir Pressure']).any(axis=1)].index[0]
    CO2_base_idx =     ip_init[ip_init.isin(['Base of CO2']).any(axis=1)].index[0]
    main_barrier_idx = ip_init[ip_init.isin(['Main barrier']).any(axis=1)].index[0]
    barrier_k_idx =    ip_init[ip_init.isin(['Barrier permeability']).any(axis=1)].index[0]

    well = dict()

    #Parse and read well header information
    well['header'] = dict()
    well['header']['name'] = ip_data.iloc[0, 1]
    well['header']['rkb'] = ip_data.iloc[1, 1]
    well['header']['water_depth'] = ip_data.iloc[2, 1]
    well['header']['ML'] = ip_data.iloc[3, 1]
    well['header']['TD'] = ip_data.iloc[4, 1]
    well['header']['water_temp'] = ip_data.iloc[5, 1]
    well['header']['temp_grad'] = ip_data.iloc[6, 1] / 1e3

    #Parse and read initialization parameters
    well['init'] = dict()
    P_rsrv_i = ip_init[resrv_P_idx+1:CO2_base_idx].dropna(how='all', axis=1)
    P_rsrv_i = P_rsrv_i.dropna(how='all')
    P_rsrv_i.columns = P_rsrv_i.iloc[0]
    P_rsrv_i = P_rsrv_i.drop(P_rsrv_i.index[0])
    P_rsrv_i = P_rsrv_i.squeeze()
    P_rsrv_i.index.name = None
    P_rsrv_i = P_rsrv_i.to_dict()

    barrier_k = ip_init[barrier_k_idx+1:].dropna(how='all', axis=1)
    barrier_k = barrier_k.dropna(how='all')
    barrier_k.columns = barrier_k.iloc[0]
    barrier_k = barrier_k.drop(barrier_k.index[0])
    barrier_k = barrier_k.squeeze()
    barrier_k.set_index('quality', inplace=True)
    barrier_k = barrier_k.to_dict()


    well['init']['P_init'] = P_rsrv_i

    well['init']['CO2_base_MSL'] = ip_init[CO2_base_idx:].dropna(how='all', axis=1).iloc[0,1]
    well['init']['main_barrier_MSL'] = ip_init[main_barrier_idx:].dropna(how='all', axis=1).iloc[0,1]
    well['init']['barrier_k_mD'] = barrier_k

    #Parse and read drilling data
    drilling_df = ip_data.iloc[drilling_idx + 2:casing_idx].dropna(how='all', axis=1)
    drilling_df = drilling_df.dropna(how='all')
    drilling_df = drilling_df.reset_index(drop=True)

    drilling_df.rename(columns={0:'top_RKB', 
                                1:'bottom_RKB', 
                                2:'diameter_in'}, inplace=True)

    well['drilling'] = drilling_df.to_dict()


    #Parse and read casing/tubing data
    casings_df = ip_data.iloc[casing_idx + 2:barriers_idx].dropna(how='all', axis=1)
    casings_df = casings_df.dropna(how='all')
    casings_df = casings_df.reset_index(drop=True)

    casings_df.rename(columns={0:'top_RKB', 
                                1:'bottom_RKB', 
                                2:'diameter_in', 
                                3:'top_CB_RKB',  
                                4:'bottom_CB_RKB',  
                                5:'shoe_bool'}, inplace=True)


    well['casings'] = casings_df.to_dict()


    #Parse and read barrier data
    barriers_df = ip_data.iloc[barriers_idx + 2:geology_idx].dropna(how='all', axis=1)
    barriers_df = barriers_df.dropna(how='all')
    barriers_df = barriers_df.reset_index(drop=True)

    barriers_df.rename(columns={0:'barrier_name', 
                                1:'barrier_type', 
                                2:'top_RKB', 
                                3:'bottom_RKB'}, inplace=True)



    well['barriers'] = barriers_df.to_dict()


    #Parse and read geology data
    geology_df = ip_data.iloc[geology_idx + 2:].dropna(how='all', axis=1)
    geology_df = geology_df.dropna(how='all')
    geology_df = geology_df.reset_index(drop=True)

    geology_df.rename(columns={0:'top_RKB', 
                                1:'geotop_name', 
                                2:'bool_reservoir'}, inplace=True)

    geology_df['top_MSL'] =  geology_df['top_RKB'] - well['header']['rkb']
    geology_df['base_MSL'] = geology_df['top_MSL'] - geology_df['top_MSL'].diff(periods=-1)
    geology_df.loc[geology_df.index.max(), 'base_MSL'] = well['header']['TD'] - well['header']['rkb']

    well['geology'] = geology_df.to_dict()

    return well


def lookup_rho(p,t, PVT_P, PVT_T, PVT_RHO):
    ''' Find the index in the p and t arrays that are closest
        to the look-up values.
        Consider later to get the two closest (on each side of the true value)
        and use interpolation. As now it only picks the closest value
    '''

    P = PVT_P
    T = PVT_T
    RHO = PVT_RHO
    p_idx1, p_idx2 = find_nearest_idx(P,p)
    t_idx1, t_idx2 = find_nearest_idx(T,t)

    tvals = [T[t_idx1], T[t_idx2]]
    pvals = [P[p_idx1], P[p_idx2]]
    
    rho_11 = RHO.T[t_idx1][p_idx1]
    rho_21 = RHO.T[t_idx2][p_idx1]
    rho_12 = RHO.T[t_idx1][p_idx2]
    rho_22 = RHO.T[t_idx2][p_idx2]
    
    rho    = bilinear_interp(t,p,tvals, pvals,[rho_11, rho_21, rho_12, rho_22])

    return rho


def find_nearest_idx(vec,val):
   ''' Only finds the index in the array to the nearest value (val)
       Assumes that the list is sorted
       Consider returning the indexes for the two closest values
       (above and below)
   '''
   idx1 = np.abs(vec-val).argmin()
   if vec[idx1] > val:     #The closest value is ABOVE the look-up value val
      idx2 = idx1 -1 
      return idx2, idx1
   else:
       idx2 = idx1 + 1     #The cosest value is BELOW the look-up value
       return idx1, idx2


def bilinear_interp(x,y, xvals, yvals, vals):
    ''' Bilinear interpolation accoring to https://en.wikipedia.org/wiki/Bilinear_interpolation
        f(x,y) = 1/((x2-x1)(y2-y1)) * [x2-x, x-x1] * [f11, f12, * [y2-1]
                                                      f21, f22]   [y-y1]
   (x1,y2)            (x2,y2)
    f12                f22 
      *----------------*
      |                |
      |                |
      |                |
      |                |
      *----------------*
  (x1,y1)             (x2,y1)
   f11                 f21


   Typically
     P
     ^
     |
     |
     ---------> T
    '''
    a  = 1/((xvals[1] - xvals[0])*(yvals[1]-yvals[0]))
    xx = np.array([[xvals[1] -x],[x-xvals[0]]], dtype='float32')
    f  = np.array(vals).reshape(2,2).T
    yy = np.array([[yvals[1]-y], [y - yvals[0]]], dtype='float32')
    b  = np.matmul(f,yy)

    return a*np.matmul(xx.T,b)[0,0]  #This is a 1x1 matrix. Return only a scalar


    """Simple integradtion to get the hydrostatic pressure at a given depth"""
    # def get_hydrostatic_P(ref_z):
    T, P, RHO_CO2, RHO_H2O = get_pvt()
    G = 9.80665    #m/s2 depth acceleration


    dz = 1 #sampling rate

    TD_MSL = well_header['well_td_rkb']-well_header['well_rkb']
    z_vector = np.arange(0, int(TD_MSL)+2, dz)

    #Create dataframe for storing pressures and temperature
    hs_P_df = pd.DataFrame(data=z_vector, columns = ['depth_msl'])

    #Compute temperature. Constant in water column and as a function of input geothermal gradient
    hs_P_df['temp'] = well_header['sf_temp'] + (hs_P_df['depth_msl']-well_header['water_depth'])*well_header['temp_grad']
    hs_P_df.loc[hs_P_df['depth_MSL']<well_header['sf_depth_msl'], 'temp'] = well_header['water_temp']


    #Integrate hydrostatic pressure
    p_MSL = 1.01325 # Pressure at MSL

    p0 = p_MSL
    z0 = 0

    t0 = np.interp(z0, hs_P_df['depth_MSL'], hs_P_df['Temp'])

    rho_vec = [lookup_rho(p0, t0, P, T, RHO_H2O)]

    hs_P_df['hs_P'] = p_MSL

    p = p0
    for idx, t in hs_P_df['Temp'][1:].items():
        rho = lookup_rho(p, t, P, T, RHO_H2O)
        p += (rho*G*dz)*1e-5
        rho_vec.append(rho)
        hs_P_df.loc[idx, 'hs_P'] = p

    ref_P = np.interp(ref_z, hs_P_df['depth_MSL'], hs_P_df['hs_P'])

    return hs_P_df

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
    """Simple integradtion to get the hydrostatic pressure at a given depth"""
    # def get_hydrostatic_P(ref_z):
    T, P, RHO_CO2, RHO_H2O = get_pvt()
    G = 9.80665    #m/s2 depth acceleration

    TD_MSL = well_header['well_td_rkb']-well_header['well_rkb']
    z_vector = np.arange(0, int(TD_MSL)+2, dz)

    #Create dataframe for storing pressures and temperature
    hs_P_df = pd.DataFrame(data=z_vector, columns = ['depth_msl'])

    #Compute temperature. Constant in water column and as a function of input geothermal gradient
    hs_P_df['temp'] = well_header['sf_temp'] + (hs_P_df['depth_msl']-well_header['sf_depth_msl'])*(well_header['geo_tgrad']/1000)
    hs_P_df.loc[hs_P_df['depth_msl']<well_header['sf_depth_msl'], 'temp'] = well_header['sf_temp']


    #Integrate hydrostatic pressure
    p_MSL = 1.01325 # Pressure at MSL

    p0 = p_MSL
    z0 = 0

    t0 = np.interp(z0, hs_P_df['depth_msl'], hs_P_df['temp'])

    rho_vec = [lookup_rho(p0, t0, P, T, RHO_H2O)]

    hs_P_df['hs_p'] = p_MSL

    p = p0
    for idx, t in hs_P_df['temp'][1:].items():
        rho = lookup_rho(p, t, P, T, RHO_H2O)
        p += (rho*G*dz)*1e-5
        rho_vec.append(rho)
        hs_P_df.loc[idx, 'hs_p'] = p
    hs_P_df['RHOH2O'] = rho_vec

    return hs_P_df


def fraction_float(frac_str):
    frac_str = frac_str.split()
    integer = frac_str[0]
    rational = eval(integer)
    if len(frac_str)>1:
        fraction = frac_str[1]
        rational += eval(fraction)
    return rational


def float_to_fraction_inches(d_in):
        """Converts float number fot integer fraction string"""
        int_d = int(d_in)
        remainder = d_in - int_d
        if remainder > 0:
                fraction = remainder.as_integer_ratio()
                fraction_str = f'{fraction[0]}/{fraction[1]}'
                d_fmt = f'{int_d} {fraction_str}"'
                return d_fmt
        else:
                d_fmt = f'{int_d}"'
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

            table_str = '\n'.join(sec_lines[1:])

            if table_title.lower() == 'well_header':
                table = pd.read_csv(io.StringIO(table_str), names=['attribute', 'value'], header=None, index_col=0, usecols=[0,1]).squeeze()
                for attribute, value in table.items():
                    try:
                        table[attribute] = float(value)
                    except:
                        table[attribute] = value


            elif table_title.lower() == 'reservoir_pressure':
        
                table = pd.read_csv(io.StringIO(table_str), index_col=False).squeeze()
                print(table)

           

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


def write_csv(my_well):
        wellname = my_well.header['well_name']

        file_path = wellname.replace('/', '_')
        file_path = file_path.replace(' ', '_')
        file_path = f'{file_path}_GaP_input.csv'



        # Create a StringIO instance
        string_io = io.StringIO()

        # Write the string into the StringIO instance
        string_io.write('input_data\n\nwell_header\n')

        units = ['m', 'mTVDMSL', 'mRKB', 'degC', 'degC/km']

        counter=0
        for key,value in my_well.header.items():
                if counter>=1:
                        string_io.write(f'{key}, {value}, {units[counter-1]}\n')
                else:
                        string_io.write(f'{key}, {value}\n')

        counter+=1

        string_io.write('\n\ndrilling\n')

        df = pd.DataFrame(my_well.drilling)
        df.to_csv(string_io, index=False)


        string_io.write('\ncasing_cement\n')

        df = pd.DataFrame(my_well.casings)
        df.to_csv(string_io, index=False)


        string_io.write('\nbarriers\n')

        df = pd.DataFrame(my_well.barriers)
        df.to_csv(string_io, index=False)

        string_io.write('\n\ngeology\n')

        df = pd.DataFrame(my_well.geology)
        df.to_csv(string_io, index=False)


        string_io.write('\n\nassumptions\n\nreservoir_pressure\n')

        string_io.write(','.join(my_well.reservoir_P.keys())+'\n')
        string_io.write(','.join(map(str, my_well.reservoir_P.values())))


        string_io.write(f'\n\n\nco2_datum\nco2_msl,{my_well.co2_datum}')

        string_io.write(f'\n\n\nmain_barrier\nbarrier_name,{my_well.main_barrier}')

        string_io.write(f'\n\n\nbarrier_permeability\n')

        df = pd.DataFrame(my_well.barrier_perm)
        df.to_csv(string_io, index=False)

        # Get the string content from the StringIO instance
        string_content = string_io.getvalue()

        # Save the string content to an ASCII file
        # file_path = "output.csv"
        with open(file_path, "w", encoding='utf-8-sig') as file:
                file.write(string_content)

        # Close the StringIO instance
        string_io.close()

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
    
    def process_drilling(self):
        drilling_df = pd.DataFrame(self.drilling)

        drilling_df['top_rkb']
        drilling_df['diameter_m'] = drilling_df['diameter_in'] * 0.0254
        drilling_df['top_msl'] = drilling_df['top_rkb'] - self.header['well_rkb']
        drilling_df['bottom_msl'] = drilling_df['bottom_rkb'] - self.header['well_rkb']
        self.drilling = drilling_df.to_dict()

    def process_casings(self):
        casings_df = pd.DataFrame(self.casings)
        casings_df['diameter_m']    = casings_df['diameter_in'] * 0.0254
        casings_df['top_msl']       = casings_df['top_rkb']    -   self.header['well_rkb']
        casings_df['bottom_msl']    = casings_df['bottom_rkb'] -   self.header['well_rkb']
        casings_df['toc_msl']       = casings_df['toc_rkb']    - self.header['well_rkb']
        casings_df['boc_msl']       = casings_df['boc_rkb']    - self.header['well_rkb']
        self.casings = casings_df.to_dict()

    def process_barriers(self):
        barriers_df = pd.DataFrame(self.barriers)

        barriers_df['top_msl'] =    barriers_df['top_rkb']    - self.header['well_rkb']
        barriers_df['bottom_msl'] = barriers_df['bottom_rkb'] - self.header['well_rkb']
        # barriers_df.set_index('barrier_name', inplace=True)
        self.barriers = barriers_df.to_dict()
    
    def process_geology(self):
        geology_df = pd.DataFrame(self.geology)
        geology_df = geology_df.dropna(how='all')
        geology_df = geology_df.reset_index(drop=True)

        geology_df['top_msl'] =  geology_df['top_rkb'] - self.header['well_rkb']
        geology_df['base_msl'] = geology_df['top_msl'] - geology_df['top_msl'].diff(periods=-1)
        geology_df.loc[geology_df.index.max(), 'base_msl'] = self.header['well_td_rkb'] - self.header['well_rkb']

        self.geology = geology_df.to_dict()


    
    def compute_borehole(self):
        """Routine to compute the effective open borehole. 
        It takes the original hole and substracts the diameter taken by cement bond."""

        casings_df = pd.DataFrame(self.casings)
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
        borehole[:-1, 1] = borehole[1:, 0]

        borehole_df = pd.DataFrame(data=borehole, columns=['top_msl', 'bottom_msl', 'id_m'])
        self.borehole = borehole_df.to_dict()

    
    def compute_barriers_diam(self):
        """Processes barriers data. Takes the cumputed borehole data to recompute 
        the barrier intervals in cases where the barriers are sitting along differen hole sizes"""

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
        """Processes cement bond intervals. Reads both casing and borehole sizes to estimate cement bond width"""
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
        P_init = self.reservoir_P

        for key in P_init.copy():
            if key == 'depth_msl':
                ref_z = P_init[key]
            elif key == 'RP1':
                RP1 = P_init[key]
                if np.isnan(RP1):
                    print("RP1 set as hydrostatic")
                    hydrostaticP = get_hydrostatic_P(self.header)
                    ref_P = np.interp(ref_z, hydrostaticP['depth_msl'], hydrostaticP['hs_p'])

                    self.reservoir_P['RP1'] = ref_P
            else:
                RP = P_init[key]
                
                if isinstance(RP, str):
                    if RP.startswith(("+", "-")):
                        p = self.reservoir_P['RP1'] + eval(RP)
                        print(f'{key} is set as Delta P = RP, which yields P = {p:.2f} bar')
                        self.reservoir_P[key] = self.reservoir_P['RP1'] + eval(RP)
                    else:
                        P_init.pop(key)
                        print(RP, 'ignored')
                        continue    
                
                elif np.isnan(RP):
                    P_init.pop(key)
                    continue

    def compute_CO2_pressures(self):
        well_header = self.header
        P_init = self.reservoir_P
        base_CO2 = self.co2_datum

        T, P, RHO_CO2, RHO_H2O = get_pvt()
        G = 9.80665    #m/s2 depth acceleration
        p_MSL = 1.01325 # Pressure at MSL

        get_rho_H20 = RectBivariateSpline(P, T, RHO_H2O)
        get_rho_CO2 = RectBivariateSpline(P, T, RHO_CO2)

        def get_rho(phase, p, t):
            if phase=='co2':
                rho  = get_rho_CO2(p,t)[0, 0]
            elif phase == 'h20':
                rho  = get_rho_H2O(p,t)[0, 0]


        #Integrate hydrostatic pressure
        PT_df = get_hydrostatic_P(self.header)


        #Compute Shmin
        wd = well_header['sf_depth_msl']
        WP_ML = np.interp(wd, PT_df['depth_msl'], PT_df['hs_p'])
        PT_df['Shmin'] = PT_df['hs_p']

        Shmin_query = PT_df.query('depth_msl>=@wd')

        PT_df.loc[PT_df['depth_msl']>=wd, 'Shmin'] = WP_ML + (Shmin_query['depth_msl']-wd)*0.1695


        ref_z = P_init['depth_msl']
        ref_z_hsp = np.interp(ref_z, PT_df['depth_msl'], PT_df['hs_p'])
        ref_z_temp = np.interp(ref_z, PT_df['depth_msl'], PT_df['temp'])

        ref_z, ref_z_hsp, ref_z_temp

        for key, value in P_init.items():
            if key == 'depth_msl':
                ref_z = value
                print(ref_z)
                # above_ref_query = PT_df.query('depth_MSL>=@shallowest_barrier & depth_MSL<@ref_z')
            else:
                phases_zval = [('h2o', ref_z), ('co2', base_CO2)]

                rp = key #pressure name
                p0 = value #pressure value

                for phase, ref_depth in phases_zval:
                        #crate column names in dataframe
                        colname_p   = rp+'_'+phase
                        colname_rho = rp+'_'+phase+'_rho'

                        #create empty columns for each phase
                        PT_df[colname_p] = np.nan #pressure
                        PT_df[colname_rho] = np.nan #density

                        #Assign P value at reference point if depth value exists
                        PT_df.loc[PT_df.depth_msl == ref_depth, colname_p] = p0
                        

                        #Create tuple lists for sections for integration
                        segments_list = []

                        #Split vector in two sections for iterations: upwards(-1) and downwards(+1).
                        above_ref_query = PT_df.query('depth_msl<@ref_depth')
                        segments_list.append((above_ref_query, -1))
                        
                        #below segment only evaluated for water
                        if phase == 'h2o':
                                below_ref_query = PT_df.query('depth_msl>@ref_depth')
                                segments_list.append((below_ref_query, 1))

                        #if CO2 p0 is updated to H2O pressure at CO2 datum
                        if phase == 'co2':
                                p0 = np.interp(ref_depth, PT_df['depth_msl'], PT_df[rp+'_h2o'])
                                
                                #Update P value at reference point if depth value exists
                                PT_df.loc[PT_df.depth_msl == ref_depth, colname_p] = p0

                        #interpolate temperature to given value
                        t0 = np.interp(ref_z, PT_df['depth_msl'], PT_df['temp'])
                        
                        PT_df.loc[PT_df.depth_msl == ref_depth, colname_p] = get_rho(phase, p0, t0)
                        
                        PT_df.loc[PT_df.depth_msl == ref_depth, colname_rho] = p0

                        for segment, sign in segments_list:
                                p = p0
                                z0 = ref_depth

                                for z_idx, row in segment[::sign].iterrows():
                                        t = row['temp']
                                        z = row['depth_msl']

                                        if phase == 'h2o':
                                                rho = get_rho_H20(p, t)[0,0]
                                        else:
                                                rho = get_rho_CO2(p, t)[0,0]

                                        dz = z - z0
                                        p += (rho*G*dz)*1e-5
                                        if p<p_MSL:
                                                p=p_MSL
                                        
                                        PT_df.loc[z_idx, colname_p] = p
                                        PT_df.loc[z_idx, colname_rho] = rho
                                        z0 = z

        self.pressure_CO2 = PT_df

        
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

        # Draw borehole
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

    
    def plot_pressure(self, ax = None):
        if ax is None:
             fig, ax = plt.subplots()
         
        try:
             PT_df = self.pressure_CO2
        except:
             self.compute_CO2_pressures()
             PT_df = self.pressure_CO2

        well_header =     self.header
        sf_depth = well_header['sf_depth_msl']
        barriers_df =     pd.DataFrame(self.barriers)
        geology_df =      pd.DataFrame(self.geology)


        
        #define plot spatial references
        base_deepest_rsrv = geology_df[geology_df.reservoir_flag]['base_msl'].max()
        ymax = max([base_deepest_rsrv,self.co2_datum])+100
        xmax = PT_df.query('depth_msl>@ymax')['Shmin'].iloc[0]
        xmin =  0
        
        # Draw cement plugs
        for idx, row in barriers_df.iterrows():
            barrier = ax.axhspan(row['top_msl'], row['bottom_msl'], color='lightgray', zorder=-20, label = 'cement plug')

        #Plot hydrostatic pressure gradient
        PT_df.plot(x='hs_p', y='depth_msl', ax=ax, label='$p_{hs}$', color='steelblue', lw = 0.75)

        #Plot minimum horizontal stress
        PT_df.plot(x='Shmin', y='depth_msl', ax=ax, label='$\sigma_{h min}$', color='k', lw = 0.75)

        #Plot fluid pressure scenarios
        ls_list = ['-', '--', ':']
        counter = 0

        for key in self.reservoir_P:
                if key != 'depth_msl':
                        PT_df.query('depth_msl>=@sf_depth').plot(x=key+'_h2o', y='depth_msl', ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])
                        PT_df.query('depth_msl>=@sf_depth').plot(x=key+'_co2', y='depth_msl', ax=ax, label = key, color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])

                        counter+=1
        
        #Optimize legend
        ax.legend()
        handles, labels = ax.get_legend_handles_labels()  
        lgd = dict(zip(labels, handles))
        ax.legend(lgd.values(), lgd.keys())
        
        ax.set_xlim(xmin, xmax)
        ax.set_xlabel('presure [bar]')
        ax.set_ylim(0, ymax)
        ax.invert_yaxis()



    def plot_PT(self, fig=None, ax=None):

        if fig == None:
            fig, ax = plt.subplots()


        T, P, RHO_CO2, RHO_H2O = get_pvt()

        #Plot density colormap
        rho_pcm = ax.pcolormesh(T, P, RHO_CO2, alpha=0.5)

        #Plot phase boundary and critical point
        T_CO2 = np.array([-50,-48.35,-46.69,-45.04,-43.38,-41.73,-40.08,-38.42,-36.77,-35.11,-33.46,-31.81,-30.15,-28.5,-26.84,-25.19,-23.53,-21.88,-20.23,-18.57,-16.92,-15.26,-13.61,-11.96,-10.3,-8.65,-6.99,-5.34,-3.69,-2.03,-0.38,1.28,2.93,4.58,6.24,7.89,9.55,11.2,12.86,14.51,16.16,17.82,19.47,21.13,22.78,24.43,31.05])
        P_CO2 = np.array([6.8,7.27,7.77,8.29,8.83,9.4,10,10.63,11.28,11.97,12.68,13.43,14.21,15.02,15.87,16.75,17.66,18.62,19.61,20.64,21.7,22.81,23.96,25.15,26.38,27.66,28.98,30.34,31.76,33.21,34.72,36.28,37.89,39.54,41.25,43.01,44.83,46.7,48.63,50.61,52.65,54.75,56.91,59.12,61.4,63.75,73.76])
        ax.plot(T_CO2, P_CO2, color='k', lw=1.5, label = r'$CO_2$ phase env.')
        ax.scatter(T_CO2.max(), P_CO2.max(), c='k')

        #Retrieve pressures ar well
        try:
             PT_df = self.pressure_CO2
        except:
             self.compute_CO2_pressures()
             PT_df = self.pressure_CO2        

        wd = self.header['sf_depth_msl']
        co2_datum = self.co2_datum

        #Plot fluid pressure scenarios
        ls_list = ['-', '--', ':']
        counter = 0

        ymax = 0
        for key in self.reservoir_P:
                if key != 'depth_msl':
                        PT_df.query('depth_msl>=@wd').plot(y=key+'_h2o', x='temp', ax=ax, label = '_nolegend_', color='steelblue', legend=False, lw = 0.75, ls=ls_list[counter])
                        PT_df.query('depth_msl>=@wd').plot(y=key+'_co2', x='temp', ax=ax, label = f'$CO_2$ {key}', color='firebrick', legend=True, lw = 0.75, ls=ls_list[counter])
                        
                        base_msl = PT_df.query('depth_msl>(@co2_datum)+50')[key+'_h2o'].iloc[0]

                        if base_msl > ymax:
                                ymax = base_msl

                        counter+=1

        xmax = PT_df.query('depth_msl>(@co2_datum)+50')['temp'].iloc[0]

        ax.set_ylabel('p [bar]')
        ax.set_xlabel('T [$\degree$C]')
        ax.set_xlim(1, xmax)
        ax.set_ylim(1, ymax)
        fig.colorbar(rho_pcm, label=r'$\rho_{CO_2}$ [$kg/m^3$]')

        fig.tight_layout()
        plt.show()

    @property
    def to_json(self):
        return json.dumps(self.__dict__, indent=4)