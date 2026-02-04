#!/usr/bin/env python

import os
from resdata.resfile import ResdataInitFile, ResdataRestartFile
from resdata.grid import Grid
import numpy as np
import sys
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objects as go

print(sys.argv)

ip_path = sys.argv[1]
if not os.path.isfile(ip_path):
        print('ERROR:\nFile does not exist.\nEnter a valid path')
        sys.exit(1)

print(f'file: {os.path.basename(ip_path)}')
print(f'path: {os.path.dirname(ip_path)}')

pr_path = os.path.dirname(ip_path)
simname = os.path.basename(ip_path)
simname = simname.split('.')[0]
simcase = os.path.join(pr_path,simname)


#parquet_files
file_rst_df  = os.path.join(f'{pr_path}',f'DF_rst_{simname}.parquet.gzip')
file_init_df = os.path.join(f'{pr_path}',f'DF_init_{simname}.parquet.gzip')

#Check if parquet files exists and if they are newer than the latest restart file
process = True
if os.path.isfile(file_rst_df) and os.path.isfile(file_init_df):
        if os.path.getmtime(simcase + ".UNRST") < os.path.getmtime(file_rst_df):
                process = False


#Start processing
#Get grid dimensions and coordinates
grid = Grid(simcase + ".EGRID")
init = ResdataInitFile(grid ,simcase + ".INIT")
rst = ResdataRestartFile(grid ,simcase + ".UNRST")

#Process init file
lgr_name = grid.get_lgr(0).get_name()
lgr_grid = grid.get_lgr(lgr_name)
lgr_init = lgr_grid.export_index()


# Static properties Dataframe
for key in init.keys():
        try:
                lgr_init[key] = init[key][1].numpy_view()
        except Exception:
                continue

#Create coordinate X, Y, Z
xcoord = (lgr_init.query("j==0&k==0").DX.cumsum()).values
ycoord = (lgr_init.query("i==0&k==0").DY.cumsum()).values
zcoord = (lgr_init.query("i==0&j==0").DZ.cumsum()).values

map_X = dict(zip(lgr_init.query("j==0&j==0")['i'], xcoord))
map_Y = dict(zip(lgr_init.query("i==0&k==0")['j'], ycoord))
map_Z = dict(zip(lgr_init.query("i==0&j==0")['k'], zcoord))

lgr_init['X'] = lgr_init['i'].map(map_X)
lgr_init['Y'] = lgr_init['j'].map(map_Y)
lgr_init['Z'] = lgr_init['k'].map(map_Z)

X_radius = lgr_init['X'].max()/2

lgr_init['X'] = lgr_init['X'] - lgr_init['DX']/2
lgr_init['X'] = lgr_init['X'] - X_radius
lgr_init['Y'] = lgr_init['Y'] - lgr_init['DY']/2
lgr_init['Z'] = lgr_init['Z'] - lgr_init['DZ']/2

#Retrieve time steps from restart file
tsteps = rst.timeList() #No. of timesteps and time value
n_tsteps = len(tsteps) #Number of time steps


if process:
        #Retrieve restart properties
        lgr_rst = lgr_grid.export_index() 
        lgr_rst = pd.concat([lgr_rst]*n_tsteps) #Repeat indexes the number of time steps

        t_idx = np.array(tsteps)[:,0] #Time step index
        t_idx_rst = np.repeat(t_idx,lgr_init.shape[0]) #Repeat/tile time step index the number of LGR cells

        lgr_rst['tstep'] = t_idx_rst 
        lgr_rst = lgr_rst.set_index('tstep')

        for key in rst.keys():
                if len(rst[key]) == n_tsteps*2:
                        if rst[key][1].isNumeric() and len(rst[key][1]) == lgr_grid.getGlobalSize():
                                lgr_rst[key] = np.nan
                                for idx, key_val in enumerate(rst[key]):
                                        if idx%2 == 1:
                                                lgr_rst.loc[idx//2, key] = key_val.numpy_view()

        lgr_rst.to_parquet(file_rst_df)
        lgr_init.to_parquet(file_init_df)
else:
        print('Parquet files already exist and are newer than restart file.')
        lgr_rst = pd.read_parquet(file_rst_df)
        lgr_init = pd.read_parquet(file_init_df)

# print("min PERMX", lgr_init['PERMX'].min())
lgr_init.loc[lgr_init['MULTZ'] == 0, 'PERMX'] = 1e-3

#Correct coordinates to sit at center of cell. PFT coordinates sit at end.
lgr_rst     = lgr_rst.reset_index()
mid_j_index = lgr_init.j.max()//2

Xcoord = lgr_init.query("j=={:d}&k==k.min()".format(mid_j_index)).DX.cumsum().tolist()
Xcoord = [0] + Xcoord
Xcoord = np.array(Xcoord)
Xcoord = Xcoord - Xcoord.max()/2

Ycoord = lgr_init.query("j=={:d}&i==i.min()".format(mid_j_index)).DZ.cumsum().tolist()
Ycoord = [0] + Ycoord


### Start on Dash
app = Dash(__name__)

#Names in pull down lists
var_names    = lgr_init.columns.tolist() + lgr_rst.columns.tolist()
var_names2   = ["SGAS", "None"]

#Names for freeze button
#freeze_names = ["Freeze from next zoom", "Reset"]
freeze_names = ["Freeze/Reset1", "Freeze/Reset2"]

#Time steps available in the slider
tstep_values = np.array(tsteps)[:,0]
tstep_dates  = [x.strftime("%d%b%Y") for x in np.array(tsteps)[:,1]]
slider_marks = dict(zip(tstep_values,tstep_dates))

button_style = [{'background-color': 'gray'}, {'background-color': 'red'}]
#The layout
app.layout = html.Div([
        html.Div([
                'Background',
                dcc.Dropdown(
                        options = var_names,
                        value = 'PERMX',
                        id='select_background'
                ),
        ],
                 style={'display':'inline-block', 'marginTop': '5px', 'width': '30%'}
         ),
        html.Div([
                'Foreground - overlays the other parameter with a white-red-shade',
                dcc.Dropdown(
                        options = var_names2,
                        value = 'SGAS',
                        id='select_foreground'
                ),
        ],
                 style={'display':'inline-block', 'marginTop': '5px', 'width': '30%', 'margin-left': '15px'}
         ),
        html.Div([
        html.Button("Freeze from next zoom", id="reset", n_clicks=0),
        ],
                 style={'display':'inline-block', 'marginTop': '5px', 'width': '10%', 'margin-left': '15px'}
        ),
             
        html.Div([
                dcc.Interval(id="animate", disabled=True, interval =3*1000, n_intervals=1),
                html.Div(id='slider-output-container'),
                dcc.Slider(
                        min=tsteps[0][0],
                        max=tsteps[-1][0],
                        step=1,
                        value=0,
                        id='year-slider',
                ),
                html.Button("Play/Stop", id="play", n_clicks=0, style=button_style[0]),
        ],
                style={'display':'inline-block', 'marginTop': '30px', 'width': '50%'},
       ),        
        dcc.Graph(id='graph-with-slider'),
       
])


@app.callback(
        Output('graph-with-slider', 'figure'),
        Output('slider-output-container', 'children'),
        Output('year-slider', 'value'),
        Output('reset', 'children'),
        Input('select_background', 'value'),
        Input('select_foreground', 'value'),
        Input('year-slider', 'value'),
        Input('animate', 'n_intervals'),
        Input('animate', 'disabled'),
        Input('reset', 'n_clicks')
)
def update_figure(select_background_name, select_foreground_name, selected_tstep, intervals, stop, reset):
        
        print(f"reset: {reset}")
        #if reset == 0: 
        #        reset += 1
        step = selected_tstep
        print(intervals)
        if not stop:
                step = (step + 1)%len(tsteps[:])

        if select_background_name in lgr_init.columns:
                Zvalues = lgr_init.query("j=={:d}".format(mid_j_index))[select_background_name].values
                Zvalues = Zvalues.reshape(len(Ycoord)-1, len(Xcoord)-1)
                Zmin = Zvalues.min()
                Zmax = Zvalues.max()
        else:
                Zvalues = lgr_rst.query("j=={:d} & tstep=={:}".format(mid_j_index, selected_tstep))[select_background_name].values
                Zvalues = Zvalues.reshape(len(Ycoord)-1, len(Xcoord)-1)
                Zmin = lgr_rst.query("j=={:d}".format(mid_j_index))[select_background_name].min()
                Zmax = lgr_rst.query("j=={:d}".format(mid_j_index))[select_background_name].max()

        if select_foreground_name in lgr_init.columns: #Opens up for having more than SGAS as foregound
                Zvalues_fg = lgr_init.query("j=={:d}".format(mid_j_index))[select_foreground_name].values
                Zvalues_fg = Zvalues_fg.reshape(len(Ycoord)-1, len(Xcoord)-1)
                Zmin_fg = Zvalues_fg.min()
                Zmax_fg = Zvalues_fg.max()
        elif select_foreground_name == "None":
                pass
        else: #Foreground value is a dynamic (restart) vector
                Zvalues_fg = lgr_rst.query("j=={:d} & tstep=={:}".format(mid_j_index, selected_tstep))[select_foreground_name].values
                Zvalues_fg = Zvalues_fg.reshape(len(Ycoord)-1, len(Xcoord)-1)
                Zmin_fg = lgr_rst.query("j=={:d}".format(mid_j_index))[select_foreground_name].min()
                Zmax_fg = lgr_rst.query("j=={:d}".format(mid_j_index))[select_foreground_name].max()


        i_values = lgr_init.query("j=={:d}".format(mid_j_index)).i.values.reshape(len(Ycoord)-1, len(Xcoord)-1)
        j_values = lgr_init.query("j=={:d}".format(mid_j_index)).j.values.reshape(len(Ycoord)-1, len(Xcoord)-1)
        k_values = lgr_init.query("j=={:d}".format(mid_j_index)).k.values.reshape(len(Ycoord)-1, len(Xcoord)-1)

        #These data will be available for hovering
        custom_data = np.dstack((Zvalues, i_values + 1, j_values + 1, k_values+ 1))

        #For legend title
        title    = select_background_name
        title_fg = select_foreground_name

        #Plot title
        title_plot = f'{simname}       {select_background_name} '

        #Use logarithmic scale for PERM and TRAN
        if select_background_name.startswith(tuple(['PERM', 'TRAN'])):
                title = 'log({:s})'.format(select_background_name)
                Zvalues = np.log10(Zvalues)
                Zmin = Zvalues.min()
                Zmax = Zvalues.max()


        fig = go.Figure()
        fig.layout.height = 800

        #Background color
        base_heatmap = go.Heatmap()
        base_heatmap.x = Xcoord
        base_heatmap.y = Ycoord
        base_heatmap.z = Zvalues
        base_heatmap.colorscale = 'Viridis'
        base_heatmap.colorbar.title = title
        base_heatmap.zmin = Zmin
        base_heatmap.zmax = Zmax

        if  select_foreground_name == "None":
                base_heatmap.customdata = custom_data
                base_heatmap.hovertemplate = select_background_name+':%{customdata[0]:.3f}<br>ijk:%{customdata[1]:.0f} %{customdata[2]:.0f} %{customdata[3]:.0f}'

        fig.add_trace(base_heatmap)

        #Foreground color
        if select_foreground_name != "None":
                top_heatmap = go.Heatmap()
                top_heatmap.x = Xcoord
                top_heatmap.y = Ycoord
                top_heatmap.name = None
                top_heatmap.customdata = custom_data
                top_heatmap.z = Zvalues_fg
                top_heatmap.colorscale = [[0, 'rgba(178, 34, 34, 0.)'], [1, 'rgba(178, 34, 34, 1.)']] #Red scale from white to red
                top_heatmap.colorbar.x = 1.1
                top_heatmap.colorbar.title = title_fg
                top_heatmap.zmin = Zmin_fg
                top_heatmap.zmax = Zmax_fg        
                
                top_heatmap.hovertemplate = select_foreground_name+': %{z:.7f}<br>'+select_background_name+':%{customdata[0]:.3f}<br>ijk:%{customdata[1]:.0f} %{customdata[2]:.0f} %{customdata[3]:.0f}'
                fig.add_trace(top_heatmap)
                title_plot += f" overlayed by    {select_foreground_name} "
                

        title_plot += f' @{tsteps[selected_tstep][1].strftime("%Y")}'
        fig.update_yaxes(title_text = 'Depth [m]', autorange='reversed')
        fig.update_xaxes(title_text = 'X dist [m]', range=[-4,4])
        fig.update_layout(title=title_plot, title_x=0.5, uirevision=reset)
        time_slider_text = 'Time step {}: {:s}'.format(selected_tstep, tsteps[selected_tstep][1].strftime("%d-%b-%Y")),

        print(freeze_names[reset%2])
        return fig, time_slider_text, step, freeze_names[reset%2]


@app.callback(
        Output("animate", "disabled"),
        Output("play", "style"),
        Input("play","n_clicks"),
        State("animate","disabled"),
)
def toggle(n,playing):
        print(f" -> {n}")
        style = button_style[n%2]
        if n>0:
                return not playing, style
        return playing, style


if __name__ == '__main__':
    app.run_server(debug=True)
