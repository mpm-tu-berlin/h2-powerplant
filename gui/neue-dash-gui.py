# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.
import json
import os
import shutil
import tempfile
import threading
import plotly.express as px


from dash import Dash, html, dcc, DiskcacheManager, CeleryManager, Input, Output, State, callback, dash_table
import plotly.graph_objects as go

from h2pp.optimizer import optimize_h2pp
from h2pp.generators import Jahreszeit
import datetime
import base64
import pandas as pd
from dash.exceptions import PreventUpdate

# Für die Background-Callbacks braucht man redis oder diskcache siehe https://dash.plotly.com/background-callbacks
if 'REDIS_URL' in os.environ:
    # Use Redis & Celery if REDIS_URL set as an env variable
    try:
        from celery import Celery
    except ImportError:
        raise ImportError("Celery is not installed. fiiiif.")  #todo
    celery_app = Celery(__name__, broker=os.environ['REDIS_URL'], backend=os.environ['REDIS_URL'])
    background_callback_manager = CeleryManager(celery_app)

else:
    # Diskcache for non-production apps when developing locally
    import diskcache

    cache = diskcache.Cache("./cache")
    background_callback_manager = DiskcacheManager(cache)


# Erstelle eine Dummy-Figur
dummy_fig = go.Figure()

# Füge den Text in die Mitte des Graphen ein
dummy_fig.add_annotation(
    text="Start simulation to see plot results",
    xref="paper", yref="paper",
    x=0.5, y=0.5, showarrow=False,
    font=dict(size=20, color="red"),
    align="center"
)

# Passe das Layout an, um den Hintergrund grau zu machen und die Achsen zu entfernen
dummy_fig.update_layout(
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    plot_bgcolor='lightgrey',  # ausgegrauter Hintergrund
    paper_bgcolor='lightgrey',
)

app = Dash(__name__, background_callback_manager=background_callback_manager)

app.layout = (
    html.Div([

        # Memory store reverts to the default value when the page is refreshed
        # for storing the uploaded files for consumers and generators.
        dcc.Store(id='consumer-generator-files-store'),


        html.Div(
            style={'display': 'flex', 'align-items': 'center', 'justify-content': 'space-between', 'width': '100%'},
            children=[
                html.Img(src=app.get_asset_url('img/MPM Logo Symbol.svg'), style={'height': '30px', 'width': 'auto'}),
                html.H1('H2Powerplant Tool', style={'text-align': 'center', 'flex-grow': '1'}),
                html.Img(src=app.get_asset_url('img/TU_Logo_lang_RGB_rot.svg'), style={'height': '30px', 'width': 'auto'}),
            ]
        ),

        html.Hr(style={'border': '1px solid #ccc', 'margin': '10px 0'}),

        # Erst hier die Spalten
        html.Div([

            html.Div(children=

            [

                html.H2('Basic Simulation Configuration'),
                html.Br(),
                html.Label('Simulation Interval [min]'),
                dcc.RadioItems([
                    {'label': ' 1', 'value': 1},
                    {'label': '15', 'value': 15},
                    {'label': '30', 'value': 30},
                    {'label': '60', 'value': 60},
                ], 15, id='sim-interval'),

                # I'm setting the limits only proactively, so that we wont get really really high or low values that might result in strange behavior in simulation
                html.Br(),
                html.Label('Inverter Efficiency (0,1 .. 1): '),
                dcc.Input(value=0.95, type='number', min=0.1, max=1, step=0.01, id='inverter-efficiency'),

                html.Br(),
                html.Label('H2 Market Price (350 bar) [EUR/kg], [1..100]: '),
                dcc.Input(value=12.85, type='number', min=1, max=100, step=0.05, id='h2-market-price-350'),

                html.Br(),
                html.Label('H2 Market Price (700 bar) [EUR/kg], [1..100]: '),
                dcc.Input(value=13.85, type='number', min=1, max=100, step=0.05, id='h2-market-price-700'),

                html.Br(),
                html.Br(),
                html.H2('Electrolyzer'),

                dcc.Checklist(
                    id='hide-components-electrolyzer',
                    options=[
                        {'label': 'Disable electrolyzer component', 'value': 'hide'}
                    ],
                    value=[]
                ),
                html.Div(id='electrolyzer-components-container', children=[
                    html.Br(),
                    html.Br(),
                    html.Label('Electrolyzer Power Range [kW]: '),
                    dcc.RangeSlider(min=100, max=5000, step=50, value=[200, 1000],
                                    marks={
                                        100: '100 kW',
                                        500: '500 kW',
                                        1000: '1 MW',
                                        2000: '2 MW',
                                        5000: '5 MW'
                                    },
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": True,
                                        "template": "{value} kW"
                                    },
                                    id='electrolyzer-power-range-slider'),

                    html.Br(),
                    html.Label('Electrolyzer Efficiency (0,1 .. 1): '),
                    dcc.Dropdown(
                        id='eta-electrolyzer-dropdown',
                        options=[
                            {'label': 'Vorauswahl1 (eta=0.6)', 'value': 'Vorauswahl1'},
                            {'label': 'Vorauswahl2 (eta=0.8)', 'value': 'Vorauswahl2'},
                            {'label': 'Custom', 'value': 'Custom'}
                        ],
                        value='Vorauswahl1',
                        clearable=False
                    ),
                    dcc.Input(
                        id='eta-electrolyzer-input',
                        type='number',
                        min=0.1,
                        max=1.0,
                        step=0.001,
                        value=0.6, # todo muessen wir es am anfang ggfs am besten auf den Wert von Vorauswahl1 setzen? (sonst wird dieser wert genommen wenn wir nix ändern)
                        disabled=True
                    ),

                    html.Br(),
                    html.Br(),
                ]),


                html.Br(),
                html.Br(),
                html.H2('Fuel Cell'),

                dcc.Checklist(
                    id='hide-components-fuelcell',
                    options=[
                        {'label': 'Disable fuel cell component', 'value': 'hide'}
                    ],
                    value=[]
                ),
                html.Div(id='fuelcell-components-container', children=[
                    html.Br(),
                    html.Br(),
                    html.Label('Fuel Cell Power Range [kW]: '),
                    dcc.RangeSlider(min=25, max=500, step=25, value=[50, 200],
                                    marks={
                                        25: '25 kW',
                                        100: '100 kW',
                                        200: '200 kW',
                                        500: '500 kW'
                                    },
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": True,
                                        "template": "{value} kW"
                                    },
                                    id='fuelcell-power-range-slider'),

                    html.Br(),
                    html.Label('Fuel Cell Efficiency Electric (0,1 .. 1): '),
                    dcc.Dropdown(
                        id='eta-fuelcell-dropdown',
                        options=[
                            {'label': 'Vorauswahl1 (eta_el=0.5, eta_th=0.3 -> overall 0.8)', 'value': 'FC_Vorauswahl1'},
                            {'label': 'Vorauswahl2 (eta_el=0.38, eta_th=0.245 -> overall 0.625)', 'value': 'FC_Vorauswahl2'},
                            {'label': 'Custom', 'value': 'Custom'}
                        ],
                        value='FC_Vorauswahl1',
                        clearable=False
                    ),
                    html.Br(),
                    html.Label('Fuel Cell Efficiency Electric (0,1 .. 1): '),
                    dcc.Input(
                        id='eta-el-fuelcell-input',
                        type='number',
                        min=0.1,
                        max=1.0,
                        step=0.001,
                        value=0.4, # arbitrary value, will be overwritten by the initial dropdown selection anyway
                        disabled=True
                    ),

                    html.Label('Fuel Cell Efficiency Thermal (0,1 .. 1): '),
                    dcc.Input(
                        id='eta-th-fuelcell-input',
                        type='number',
                        min=0.1,
                        max=1.0,
                        step=0.001,
                        value=0.3, # arbitrary value, will be overwritten by the initial dropdown selection anyway
                        disabled=True
                    ),

                    html.Br(),
                    html.Br(),
                ]),

                html.Br(),
                html.Br(),
                html.H2('Tank'),

                dcc.Checklist(
                    id='hide-components-tank',
                    options=[
                        {'label': 'Disable tank component', 'value': 'hide'}
                    ],
                    value=[]
                ),

                # todo: ggfs compress_before_storage hier rein als Auswahlmöglichkeit
                html.Div(id='tank-components-container', children=[
                    html.Br(),
                    html.Br(),
                    html.Label('Tank Storage Range [kg]: '),
                    dcc.RangeSlider(min=20, max=1000, step=20, value=[200, 500],
                                    marks={
                                        20: '20 kg',
                                        100: '100 kg',
                                        250: '250 kg',
                                        500: '500 kg',
                                        1000: '1000 kg'
                                    },
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": True,
                                        "template": "{value} kg"
                                    },
                                    id='tank-capacity-range-slider'),

                    html.Br(),
                    html.Br(),
                ]),

                html.Br(),
                html.Br(),
                html.H2('Reference Battery'),
                html.Div(children=[
                    html.Br(),
                    html.Br(),
                    html.Label('Reference Battery Capacity Range [kWh]: '),
                    dcc.RangeSlider(min=600, max=34000, step=100, value=[6000, 15000],
                                    marks={
                                        1000: '1000 kWh',
                                        5000: '5000 kWh',
                                        10000: '10000 kWh',
                                        20000: '20000 kWh',
                                        30000: '30000 kWh'
                                    },
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": True,
                                        "template": "{value} kWh"
                                    },
                                    id='battery-capacity-range-slider'),

                    html.Br(),
                    html.Br(),
                ]),

            ], style={'padding': 10, 'flex': 1}),

            html.Div(children=[


                html.H2("BDEW Load Profile"),
                html.P("Load profile for consumption of the micro grid."),

                dcc.Checklist(
                    id='hide-components-bdew',
                    options=[
                        {'label': 'Do not use BDEW calculation', 'value': 'hide'}
                    ],
                    value=[]
                ),

                html.Div(id='bdew-components-container', children=[
                    html.Br(),
                    html.Br(),

                    # Input field for yearly consumption in kWh
                    html.Label("Yearly consumption [kWh]:"),
                    dcc.Input(id="yearly-consumption-microgrid", type="number", min=0, value=100000),
                    html.Br(),
                    html.Label('Customer group: '),
                    dcc.Dropdown(
                        id='bdew-customer-group-dropdown',
                        options=[
                            {'label': 'H0', 'value': 'H0'},
                            {'label': 'G0', 'value': 'G0'},
                            {'label': 'G1', 'value': 'G1'},
                            {'label': 'G2', 'value': 'G2'},
                            {'label': 'G3', 'value': 'G3'},
                            {'label': 'G4', 'value': 'G4'},
                            {'label': 'G5', 'value': 'G5'},
                            {'label': 'G6', 'value': 'G6'},
                            {'label': 'L0', 'value': 'L0'},
                            {'label': 'L1', 'value': 'L1'},
                            {'label': 'L2', 'value': 'L2'},

                        ],
                        value='H0',
                        clearable=False
                    ),

                    html.P([
                        "Find your customer group ",
                        html.A("HERE (external link)", href="https://www.bdew.de/media/documents/Zuordnung_der_VDEW-Lastprofile_zum_Kundengruppenschluessel.pdf", target="_blank")
                    ]),

                    html.Br(),
                    html.Br(),



                ]),


                html.H2("Renewable Energies"),
                # a red hint that tells us that if PVGIS is down or the server has no access to the internet, the program may crash.
                html.P("Note: If PVGIS is down or the H2PP tool server has no access to the internet, the program may crash. Please make sure that you have internet access and that PVGIS is up and running.", style={'color': 'red'}),

                dcc.Checklist(
                    id='hide-components-photovoltaics',
                    options=[
                        {'label': 'Disable photovoltaic calculation component', 'value': 'hide'}
                    ],
                    value=[]
                ),

                html.Div(id='photovoltaics-components-container', children=[
                    html.H4("Photovoltaics Parameters"),
                    html.Br(),
                    html.Label("PV Peak Power [kWp]"),
                    dcc.Input(id="pv_peak_power", type="number", value=1000, min=0, max=1e6),
                    html.Br(),
                    html.Br(),
                    html.Label("PV Tilt angle from horizontal plane"),
                    dcc.Slider(min=0, max=90, value=0, id='pv_tilt_slider',
                               tooltip={"placement": "bottom", "always_visible": True}),
                    html.Br(),
                    html.Br(),
                    html.Label("PV Azimuth Orientation (azimuth angle) of the (fixed) plane. Clockwise from north (north=0, east=90, south=180, west=270). "),
                    dcc.Slider(min=0, max=359, value=180, id='pv_azimuth_slider',
                               tooltip={"placement": "bottom", "always_visible": True}),
                    html.Br(),
                    html.Br(),
                    html.Label("PV Technology"),
                    dcc.Dropdown(['crystSi', 'CIS', 'CdTe'], 'crystSi', id='pv_techchoice_dropdown'),

                    html.H4("Geo Coordinates"),

                    html.P("Note that the simulation will only care for the values inside the latitude and longitude fields. Make sure that these values are correct before proceeding."),
                    html.P("You can either enter an address and press the 'Geocode' button to get the latitude and longitude, or you can manually enter the latitude and longitude."),
                    html.P("The map will show the location based on the latitude and longitude values after you either did geocoding or manually entered the values and pressed the 'Update Map and Try Reverse Geocode' button."),
                    html.P("Note that the geocoding is done by the Nominatim geocoder from OpenStreetMap and is not 100% guaranteed to always work, so make sure to check the values after geocoding."),
                    # Checkbox to enable manual input of latitude and longitude
                    dcc.Checklist(id="pv_manual_lat_lon", options=[{"label": "Manually enter Latitude and Longitude", "value": "manual_input"}], value=[]),

                    # Input and button for geocoding
                    html.Div([
                        html.Label("Address"),
                        dcc.Input(id="pv_geocode_address", type="text", value="Berlin"),
                        html.Button("Geocode", id="pv_button_geocode"),
                    ]),

                    # Inputs for Latitude and Longitude, defaulting to Berlin
                    html.Label("Latitude"),
                    dcc.Input(id="pv_latitude", type="number", min=-90, max=90, value=52.52),
                    html.Br(),
                    html.Br(),
                    html.Label("Longitude"),
                    dcc.Input(id="pv_longitude", type="number", min=-180, max=180, value=13.405),

                    # Button to update the map / reverse geocode when the lat/long is changed
                    html.Button("Update Map and Try Reverse Geocode", id="pv_button_reverse_geocode_and_update_map"),

                    # A fig holder that will show the location
                    dcc.Graph(id="pv_geo_map"),


                ]),


                html.H2("Generators and Consumers (from file and constant values)"),
                html.Div([

                    # Selector for constant value or time series file:
                    html.Label('Select type of data: '),
                    dcc.Dropdown(
                        id='consumer-generator-data-type-dropdown',
                        options=[
                            {'label': 'Constant Value', 'value': 'constant_power'},
                            {'label': 'Time Series (from CSV File)', 'value': 'time_series'}
                        ],
                        placeholder='Select data type',
                        value="constant_power",
                        style={'margin': '10px'}
                    ),

                    html.Br(),

                    html.Div(id='import-data-type-ts-file-container', children=[

                        # Input form
                        dcc.Upload(
                            id='consumer-generator-upload-data',
                            children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
                            style={
                                'width': '100%',
                                'height': '60px',
                                'lineHeight': '60px',
                                'borderWidth': '1px',
                                'borderStyle': 'dashed',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'margin': '10px'
                            },
                            multiple=False
                        ),
                        html.Br(),

                        html.Label('What does the data represent (only one day or a full year?) '),
                        dcc.Dropdown(
                            id='ts-temporal-scope-dropdown',
                            options=[
                                {'label': 'One Day', 'value': 'one_day'},
                                {'label': 'Whole Year', 'value': 'whole_year'}
                            ],
                            placeholder='Select temporal scope',
                            value="",
                            style={'margin': '10px'}
                        ),

                    ]),

                    html.Div(id='import-data-type-constant-value-container', children=[
                        html.Label('Enter constant power value [kW] (note that you need to convert e.g. kg/h to kW beforehand): '),
                        dcc.Input(
                            id='consumer-generator-constant-power-input',
                            type='number',
                            placeholder='Enter constant power value',
                            style={'margin': '10px'}
                        ),
                    ]),

                    html.Br(),
                    html.Div(id='output-file-name-upload'),
                    html.Label('Identifier for component (between 1 and 12 characters; only A..Z, a..z, 0-9 or underscore allowed): '),
                    dcc.Input(
                        id='consumer-generator-caption-input',
                        type='text',
                        placeholder='Enter identifier for component',
                        pattern=r'^[a-zA-Z0-9_]{1,12}$',
                        style={'margin': '10px'}
                    ),

                    html.Br(),

                    html.Label('Consumer or Generator? '),
                    dcc.Dropdown(
                        id='ts-consumer-generator-dropdown',
                        options=[
                            {'label': 'Consumer', 'value': 'consumers'},
                            {'label': 'Generator', 'value': 'generators'}
                        ],
                        placeholder='Select type of component',
                        value="",
                        style={'margin': '10px'}
                    ),
                    html.Br(),
                    html.Label('Select energy type: '),
                    dcc.Dropdown(
                        id='ts-energy-type-dropdown',
                        options=[
                            {'label': 'Hydrogen', 'value': 'hydrogen'},
                            {'label': 'AC Electricity', 'value': 'electricity_ac'},
                            {'label': 'DC Electricity', 'value': 'electricity_dc'}
                        ],
                        placeholder='Select energy type',
                        value="",
                        style={'margin': '10px'}
                    ),

                    html.Div(id='hydrogen-pressure-selector-container', children=[
                        html.Label('Select hydrogen pressure: '),
                        dcc.Dropdown(
                            id='consumer-generator-hydrogen-pressure-dropdown',
                            # options initially left empty: the cg_set_hydrogen_pressure_options callback will fill the options with the values depending on the selected component type (consumer or generator)
                            options=[

                            ],
                            placeholder='Select hydrogen pressure',
                            value="",
                            style={'margin': '10px'}
                        ),
                    ],
                             style={'display': 'none'}),  # Initially hide the hydrogen pressure selector),

                    html.Button('Add', id='consumer-generator-add-button', n_clicks=0, style={'margin': '10px'}),

                    # Table to show added files
                    # in Div container scrollable gepackt, damit es nicht die ganze Seite aufbläht

                    html.Br(),

                    html.Div([
                        dash_table.DataTable(
                            id='consumer-generator-files-table',
                            columns=[
                                {'name': 'No.', 'id': 'lfd_id'},
                                {'name': 'File Name', 'id': 'file_name'},
                                {'name': 'Caption', 'id': 'caption'},
                                {'name': 'Temporal Scope', 'id': 'temporal_scope'},
                                {'name': 'Type', 'id': 'type'},
                                {'name': 'Energy Type', 'id': 'energy_type'},
                                {'name': 'Hydrogen Pressure [bar]', 'id': 'hydrogen_pressure'},
                                {'name': 'Constant Power Value [kW]', 'id': 'power_value'},
                                {'name': 'Data Type', 'id': 'data_type'}
                            ],
                            row_deletable=True,
                            data=[],
                            style_table={'margin': '10px'}
                        ),
                    ], style={'overflowX': 'scroll', 'display': 'inline-block', 'width': '40em'}),

                    html.Br(),
                    html.Br(),


                ]),


                html.H2("Run Simulation"),

                html.Br(),
                html.Label('Population size for genetic algorithm: '),
                dcc.Input(
                    id='pop-size-input',
                    type='number',
                    min=10,
                    max=500,
                    step=1,
                    value=50,
                ),

                html.Br(),
                html.Label('Number of generations for genetic algorithm: '),
                dcc.Input(
                    id='n-gen-input',
                    type='number',
                    min=10,
                    max=100,
                    step=1,
                    value=20,
                ),

                html.Progress(id="simulation_progress_bar", max=0.91),

                html.Button(id="start_sim_button_id", children="Run Job!"),
                #dcc.Loading(id="loading", children=[html.Div(id="loading-output")], type="default"),
                html.Button(id="cancel_sim_button_id", children="Cancel Running Job!"),




            ], style={'padding': 10, 'flex': 1})
        ], style={'display': 'flex', 'flexDirection': 'row'}),
        # dann jetzt der full-width container für plot ergebnisse
        html.Hr(style={'border': '1px solid #ccc', 'margin': '10px 0'}),
        html.Div([
            html.H2("Simulation Results H2Powerplant", style={'text-align': 'center'}),
            dcc.Tabs([
                dcc.Tab(label='Summer Simulation', children=[
                    dcc.Graph(id="graph_summer", figure=dummy_fig)
                ]),
                dcc.Tab(label="Transitional Simulation", children=[
                        dcc.Graph(id="graph_transitional", figure=dummy_fig)
                ]),
                dcc.Tab(label="Winter Simulation", children=[
                    dcc.Graph(id="graph_winter", figure=dummy_fig)
                ]),
                dcc.Tab(label="TCO Plot", children=[
                    dcc.Graph(id="graph_tco_base", figure=dummy_fig)
                ]),
            ]),

            html.Br(),
            html.Br(),

            html.H2("Simulation Results Battery Reference Case", style={'text-align': 'center'}),
            html.H4("for the best found solution in the given kWh Battery interval"),
            dcc.Tabs([
                dcc.Tab(label='Summer Simulation', children=[
                    dcc.Graph(id="graph_batt_ref_summer", figure=dummy_fig)
                ]),
                dcc.Tab(label="Transitional Simulation", children=[
                        dcc.Graph(id="graph_batt_ref_transitional", figure=dummy_fig)
                ]),
                dcc.Tab(label="Winter Simulation", children=[
                    dcc.Graph(id="graph_batt_ref_winter", figure=dummy_fig)
                ]),
                dcc.Tab(label="TCO Plot", children=[
                    dcc.Graph(id="graph_batt_ref_tco", figure=dummy_fig)
                ]),
            ]),

            html.H2("Simulation Results Status Quo Reference Case", style={'text-align': 'center'}),
            dcc.Tabs([
                dcc.Tab(label='Summer Simulation', children=[
                    dcc.Graph(id="graph_status_quo_ref_summer", figure=dummy_fig)
                ]),
                dcc.Tab(label="Transitional Simulation", children=[
                        dcc.Graph(id="graph_status_quo_ref_transitional", figure=dummy_fig)
                ]),
                dcc.Tab(label="Winter Simulation", children=[
                    dcc.Graph(id="graph_status_quo_ref_winter", figure=dummy_fig)
                ]),
                dcc.Tab(label="TCO Plot", children=[
                    dcc.Graph(id="graph_status_quo_ref_tco", figure=dummy_fig)
                ]),
            ]),

            html.Br(),
            html.H2("Cost results / TCO"),
            html.P("Cost results will be displayed here."),

        ]),

        html.Br(),
        html.P("Copyright Stuff")

    ], style={'margin': 15}),
)


# callback ist redis/diskcache somehow - https://dash.plotly.com/background-callbacks
@callback(
    output=[
            Output("graph_summer", "figure"),
            Output("graph_transitional", "figure"),
            Output("graph_winter", "figure"),
            Output("graph_tco_base", "figure"),
            Output("graph_batt_ref_summer", "figure"),
            Output("graph_batt_ref_transitional", "figure"),
            Output("graph_batt_ref_winter", "figure"),
            Output("graph_batt_ref_tco", "figure"),
            Output("graph_status_quo_ref_summer", "figure"),
            Output("graph_status_quo_ref_transitional", "figure"),
            Output("graph_status_quo_ref_winter", "figure"),
            Output("graph_status_quo_ref_tco", "figure")
        ],
    inputs=Input("start_sim_button_id", "n_clicks"),
    state=[
        State('hide-components-electrolyzer', 'value'),
        State('eta-electrolyzer-input', 'value'),
        State('electrolyzer-power-range-slider', 'value'),
        State('hide-components-fuelcell', 'value'),
        State('eta-th-fuelcell-input', 'value'),
        State('eta-el-fuelcell-input', 'value'),
        State('fuelcell-power-range-slider', 'value'),
        State('hide-components-tank', 'value'),
        State('tank-capacity-range-slider', 'value'),
        State('battery-capacity-range-slider', 'value'),
        State('inverter-efficiency', 'value'),
        State('h2-market-price-350', 'value'),
        State('h2-market-price-700', 'value'),
        State('sim-interval', 'value'),
        State('hide-components-bdew', 'value'),
        State('bdew-customer-group-dropdown', 'value'),
        State('yearly-consumption-microgrid', 'value'),
        State('hide-components-photovoltaics', 'value'),
        State('pv_peak_power', 'value'),
        State('pv_tilt_slider', 'value'),
        State('pv_azimuth_slider', 'value'),
        State('pv_techchoice_dropdown', 'value'),
        State('pv_latitude', 'value'),
        State('pv_longitude', 'value'),
        State('pop-size-input', 'value'),
        State('n-gen-input', 'value'),
        State('consumer-generator-files-store', 'data'),


    ],
    background=True,
    running=[
        (Output("start_sim_button_id", "disabled"), True, False),
        (Output("cancel_sim_button_id", "disabled"), False, True),
    ],
    cancel=[Input("cancel_sim_button_id", "n_clicks")],
    prevent_initial_call=True
)


def update_result_plot(n_clicks, hide_electrolyzer_checkbox_value, eta_electrolyzer, electrolyzer_power_range,
                       hide_fuelcell_checkbox_value, eta_th_fuelcell, eta_el_fuelcell, fuelcell_power_range,
                       hide_tank_checkbox_value, tank_capacity_range, battery_capacity_range,
                       inverter_efficiency, h2_market_price_350, h2_market_price_700, sim_interval, hide_bdew_checkbox_value, bdew_customer_group, yearly_consumption_microgrid,
                          hide_photovoltaics_checkbox_value, pv_peak_power, pv_tilt_slider, pv_azimuth_slider, pv_techchoice_dropdown, pv_latitude, pv_longitude,
                       pop_size, n_gen,
                       data):

    # eta_electrolyzer kommt aus dem State (d.h. erst inputs, dann states)
    with tempfile.TemporaryDirectory() as temp_dir:

        datapath = os.path.join(os.path.dirname(__file__), "base_config")
        # common_data_path = os.path.join(os.path.dirname(__file__), "..", "MA_Fallbeispiele", "Common_Data")

        print(temp_dir)
        # Copy the config file and the contents of its folder to the temp dir
        # Destination may not exist or we get an error. either set dirs_exist_ok=True or set a non-existing subfolder..
        destination = shutil.copytree(datapath, os.path.join(temp_dir, 'subdirectory'))
        # shutil.copytree(common_data_path, os.path.join(temp_dir, 'Common_Data'))

        print(destination)
        file_path = os.path.join(destination, "config_base.json")

        # Modify the config file
        with open(file_path) as user_file:
            parsed_json = json.load(user_file)

        # todo später wird hier die JSON komplett neu erstellt und NIX kopiert. Tempdir brauchen wir natürlich trotzdem

        keys_to_check = ['consumers', 'generators', 'electrolyzer', 'fuelcell', 'tank', 'battery']
        for key in keys_to_check:
            if key in parsed_json.keys():
                raise ValueError(f"{key} key already in config file. Please ensure that the config file only contains the information not explicitly set using the GUI!")


        parsed_json['consumers'] = []
        parsed_json['generators'] = []

        data = data or {'all_components': []} # If no data is present, set it to an empty dict. Otherwise, we will get an error when trying to access the 'all_components' key

        # iterieren durch die eingegebenen Consumers und Generators und sie hinzu fügen.
        for component_dict in data['all_components']:

            type_cmp = component_dict['type'] # 'consumers' or 'generators'

            prefix = "Consumer_" if type_cmp == 'consumers' else "Generator_"


            if component_dict['data_type'] == 'constant_power':

                # Add the component to the config file
                obj_to_append = {
                        "name": prefix + component_dict['caption'],
                        "energy_type": component_dict['energy_type'],
                        "calculation_type": "constant_power",
                        "parameters": {
                            "power_value": component_dict['power_value']
                        }
                    }

            elif component_dict['data_type'] == 'time_series':
                # Add the component to the config file
                obj_to_append = {
                        "name": prefix + component_dict['caption'],
                        "energy_type": component_dict['energy_type'],
                        "calculation_type": "time_series",
                        "parameters": {
                            "contains": component_dict['temporal_scope']
                        }
                    }

            # If the data type is time series, recreate the file contents from the base64 string in the stored data dict
            # TODO technically, we should ensure here (or better somewhere in the base simulation) that all input files are in the correct format and have the correct columns; and throw an error if not
            if component_dict['data_type'] == 'time_series':
                base64_encoded_data = component_dict['contents'].split(',')[1]
                binary_data = base64.b64decode(base64_encoded_data)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                    temp_file.write(binary_data)
                    obj_to_append['parameters']['file_path'] = temp_file.name

            # Finally, inject hydrogen pressure if the energy type is hydrogen
            if component_dict['energy_type'] == 'hydrogen':
                obj_to_append["pressure"] = component_dict['hydrogen_pressure']

            parsed_json[type_cmp].append(obj_to_append)

        # Generators: PV manual
        if 'hide' not in hide_photovoltaics_checkbox_value:
            parsed_json['generators'].append(
                {
                    "name": "generator_pv_manual",
                    "energy_type": "electricity_dc",
                    "calculation_type": "pv_calculation",
                    "parameters": {
                        "latitude": pv_latitude,
                        "longitude": pv_longitude,
                        "peakpower": pv_peak_power,
                        "surface_tilt": pv_tilt_slider,
                        "surface_azimuth": pv_azimuth_slider,
                        "pvtechchoice": pv_techchoice_dropdown
                    }
                },
            )

        # BDEW
        if 'hide' not in hide_bdew_checkbox_value:
            parsed_json['consumers'].append(
                {
                    "name": "consumer_bdew",
                    "energy_type": "electricity_ac",
                    "calculation_type": "BDEW",
                    "parameters": {
                        "yearly_consumption": yearly_consumption_microgrid,
                        "profile": bdew_customer_group
                    }
                },
            )


        # Electrolyzer zusammenstellen..
        if 'hide' not in hide_electrolyzer_checkbox_value:
            # Electrolyzer active..
            parsed_json['electrolyzer'] = {}

            # Sanity checks?? eta in 0..1?
            parsed_json['electrolyzer']['efficiency'] = eta_electrolyzer

            # Electrolyzer Power Range

            power_range_min = electrolyzer_power_range[0]
            power_range_max = electrolyzer_power_range[1]

            if power_range_min == power_range_max:
                parsed_json['electrolyzer']['fixed_p'] = power_range_min
            else:
                parsed_json['electrolyzer']['min_p'] = power_range_min
                parsed_json['electrolyzer']['max_p'] = power_range_max

        # Fuel Cell analog
        if 'hide' not in hide_fuelcell_checkbox_value:
            # Fuel Cell active..
            parsed_json['fuelcell'] = {}

            # Sanity checks?? eta in 0..1?
            parsed_json['fuelcell']['efficiency_electric'] = eta_el_fuelcell
            parsed_json['fuelcell']['efficiency_thermal'] = eta_th_fuelcell

            # Fuel Cell Power Range

            power_range_min = fuelcell_power_range[0]
            power_range_max = fuelcell_power_range[1]

            if power_range_min == power_range_max:
                parsed_json['fuelcell']['fixed_p'] = power_range_min
            else:
                parsed_json['fuelcell']['min_p'] = power_range_min
                parsed_json['fuelcell']['max_p'] = power_range_max

        # Tank analog
        if 'hide' not in hide_tank_checkbox_value:
            # Fuel Cell active..
            parsed_json['tank'] = {}

            # Tank capacity Range
            capacity_range_min = tank_capacity_range[0]
            capacity_range_max = tank_capacity_range[1]

            if capacity_range_min == capacity_range_max:
                parsed_json['tank']['fixed_capacity'] = capacity_range_min
            else:
                parsed_json['tank']['min_capacity'] = capacity_range_min
                parsed_json['tank']['max_capacity'] = capacity_range_max

            # TODO zunächst nie auf der GUI Vorverdichten machen, da ich weder das kästchen habe, noch ein Feld um die Verdichterleistung dafür ("throughput_50bar_compressor_kg_per_hour": false) zu spezifizieren.
            parsed_json['tank']['compress_before_storing'] = False


            # Some more default properties...
            parsed_json['tank']['throughput_50bar_compressor_kg_per_hour'] = 550
            parsed_json['tank']['density_prop_factor_h2_50bar_to_30bar'] = 1.32
            parsed_json['tank']['balance_storage_level'] = True

        # Battery analog
        parsed_json['battery'] = {}

        # Battery capacity Range
        capacity_range_min = battery_capacity_range[0]
        capacity_range_max = battery_capacity_range[1]

        if capacity_range_min == capacity_range_max:
            parsed_json['battery']['fixed_capacity'] = capacity_range_min
        else:
            parsed_json['battery']['min_capacity'] = capacity_range_min
            parsed_json['battery']['max_capacity'] = capacity_range_max


        # set battery SOC defaults
        parsed_json['battery']['soc_min'] = 0.1
        parsed_json['battery']['soc_max'] = 0.9

        # anlog für die anderen auch checks ob alles im richtigen Format ist ggfs. (würde sonst eh rot angezeigt werden in GUI aber user kriegt sonst kein weiteres Feedback)
        parsed_json['base_sim_interval'] = sim_interval
        parsed_json['inverter_efficiency'] = inverter_efficiency
        parsed_json['h2_price_per_kg_350bar'] = h2_market_price_350
        parsed_json['h2_price_per_kg_700bar'] = h2_market_price_700


        # Dump the modified config file
        with open(file_path, 'w') as user_file:
            json.dump(parsed_json, user_file)

        print(parsed_json)

        # 1. H2Powerplant simulation and optimization
        # Start the optimization in a new thread
        tco_h2pp, figs = optimize_h2pp(file_path, mode="normal", pop_size=pop_size, n_gen=n_gen)
        the_fig_summer = figs[Jahreszeit.SOMMER.name]
        the_fig_transitional = figs[Jahreszeit.UEBERGANG.name]
        the_fig_winter = figs[Jahreszeit.WINTER.name]
        the_fig_tco_base = tco_h2pp.plot_stacked_bar_over_period()

        # 2. Battery Reference Case simulation
        tco_batt, batt_result = optimize_h2pp(file_path, mode="battery_ref")
        the_batt_ref_fig_summer = batt_result[Jahreszeit.SOMMER.name]
        the_batt_ref_fig_transitional = batt_result[Jahreszeit.UEBERGANG.name]
        the_batt_ref_fig_winter = batt_result[Jahreszeit.WINTER.name]
        the_batt_ref_fig_tco = tco_batt.plot_stacked_bar_over_period()

        # 3. Status Quo Reference Case simulation
        tco_sq, status_quo_result = optimize_h2pp(file_path, mode="power_grid_only_ref")
        the_status_quo_ref_fig_summer = status_quo_result[Jahreszeit.SOMMER.name]
        the_status_quo_ref_fig_transitional = status_quo_result[Jahreszeit.UEBERGANG.name]
        the_status_quo_ref_fig_winter = status_quo_result[Jahreszeit.WINTER.name]
        the_status_quo_ref_fig_tco = tco_sq.plot_stacked_bar_over_period()

        return [the_fig_summer, the_fig_transitional, the_fig_winter, the_fig_tco_base,
                the_batt_ref_fig_summer, the_batt_ref_fig_transitional, the_batt_ref_fig_winter, the_batt_ref_fig_tco,
                the_status_quo_ref_fig_summer, the_status_quo_ref_fig_transitional, the_status_quo_ref_fig_winter, the_status_quo_ref_fig_tco]

# hide or show electrolyzer components
@app.callback(
    Output('electrolyzer-components-container', 'style'),
    [Input('hide-components-electrolyzer', 'value')]
)
def toggle_components_visibility_electrolyzer(hide_values):
    if 'hide' in hide_values:
        return {'display': 'none'}
    return {'display': 'block'}

# hide or show fuel cell components
@app.callback(
    Output('fuelcell-components-container', 'style'),
    [Input('hide-components-fuelcell', 'value')]
)
def toggle_components_visibility_fuelcell(hide_values):
    if 'hide' in hide_values:
        return {'display': 'none'}
    return {'display': 'block'}

# hide or show tank components
@app.callback(
    Output('tank-components-container', 'style'),
    [Input('hide-components-tank', 'value')]
)
def toggle_components_visibility_tank(hide_values):
    if 'hide' in hide_values:
        return {'display': 'none'}
    return {'display': 'block'}

# hide or show bdew components
@app.callback(
    Output('bdew-components-container', 'style'),
    [Input('hide-components-bdew', 'value')]
)
def toggle_components_visibility_bdew(hide_values):
    if 'hide' in hide_values:
        return {'display': 'none'}
    return {'display': 'block'}


# Change electrolyzer efficiency input field based on dropdown selection
@app.callback(
    [Output('eta-electrolyzer-input', 'value'),
     Output('eta-electrolyzer-input', 'disabled')],
    [Input('eta-electrolyzer-dropdown', 'value')],
    [State('eta-electrolyzer-input', 'value')]
)
def update_eta_electrolyzer_input(selected_value, current_value):
    if selected_value == 'Vorauswahl1':
        return 0.6, True
    elif selected_value == 'Vorauswahl2':
        return 0.8, True
    else:
        return current_value, False


# Change fuel cell efficiency input field based on dropdown selection
@app.callback(
    [Output('eta-el-fuelcell-input', 'value'),
     Output('eta-el-fuelcell-input', 'disabled'),
     Output('eta-th-fuelcell-input', 'value'),
     Output('eta-th-fuelcell-input', 'disabled')
     ],
    [Input('eta-fuelcell-dropdown', 'value')],
    [State('eta-el-fuelcell-input', 'value')],
    [State('eta-th-fuelcell-input', 'value')]
)
def update_eta_fuelcell_input(selected_value, current_value_el, current_value_th):
    if selected_value == 'FC_Vorauswahl1':
        return 0.5, True, 0.3, True
    elif selected_value == 'FC_Vorauswahl2':
        return 0.38, True, 0.245, True
    else:
        return current_value_el, False, current_value_th, False



# Callback to show the time series file import fields if the data type is time series or constant power fields if the data type is constant power
@app.callback(
    Output('import-data-type-ts-file-container', 'style'),
    Output('import-data-type-constant-value-container', 'style'),
    Input('consumer-generator-data-type-dropdown', 'value')
)
def cg_show_hide_data_type_fields(data_type):
    if data_type == 'time_series':
        return {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'block'}


@callback(Output('output-file-name-upload', 'children'),
          Input('consumer-generator-upload-data', 'contents'),
          State('consumer-generator-upload-data', 'filename'),
          State('consumer-generator-upload-data', 'last_modified'))
def cg_update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        print(list_of_contents)
        the_filename = list_of_names
        the_modification_date = datetime.datetime.fromtimestamp(list_of_dates)
        the_raw_content = list_of_contents

        try:
            # Assume that the user uploaded a CSV file
            content_type, content_string = the_raw_content.split(',')

            # decoded = base64.b64decode(content_string)
            base64_string = the_raw_content

            base64_encoded_data = base64_string.split(',')[1]

            # Dekodiere den Base64-String zu binären Daten
            binary_data = base64.b64decode(base64_encoded_data)

            # Erstelle eine temporäre Datei und schreibe die binären Daten hinein
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                temp_file.write(binary_data)
                temp_file_path = temp_file.name

            # Lies die temporäre CSV-Datei mit Pandas ein
            df = pd.read_csv(temp_file_path)

            # Gib die ersten 5 Zeilen des DataFrames aus

            # print(df.head())

        except Exception as e:
            print(e)
            return html.Div([
                'There was an error processing this file.'
            ])

        return html.Div([
            html.H5(the_filename),
            html.H6(the_modification_date),

            # Gib die ersten 5 Zeilen des DataFrames aus
            dash_table.DataTable(
                df.head().to_dict('records'),
                [{'name': i, 'id': i} for i in df.columns]
            ),
        ])

    #if list_of_contents is not None:
    #    children = [
    #        parse_contents(c, n, d) for c, n, d in
    #        zip(list_of_contents, list_of_names, list_of_dates)]
    #    return children


# Callback to hide the hydrogen pressure dropdown if the energy type is not hydrogen (or consumer/generator not yet set..)
@app.callback(
    Output('hydrogen-pressure-selector-container', 'style'),
    Input('ts-energy-type-dropdown', 'value'),
    Input('ts-consumer-generator-dropdown', 'value')
)
def cg_show_hide_hydrogen_pressure_dropdown(energy_type, consumer_or_generator):
    if energy_type == 'hydrogen' and consumer_or_generator in ['consumers', 'generators']:
        return {'display': 'block'}
    else:
        return {'display': 'none'}

# Callback that will set the available hydrogen pressures to only 30 bar if the consumer/generator selection is generator and to 350 or 700 bar if the selection is consumer
@app.callback(
    Output('consumer-generator-hydrogen-pressure-dropdown', 'options'),
    Input('ts-consumer-generator-dropdown', 'value')
)
def cg_set_hydrogen_pressure_options(consumer_or_generator):
    if consumer_or_generator == 'consumers':
        return [
            {'label': '350 bar', 'value': 350},
            {'label': '700 bar', 'value': 700}
        ]
    else:
        return [
            {'label': '30 bar', 'value': 30}
        ]

@app.callback(Output('consumer-generator-files-store', 'data', allow_duplicate=True),
              [Input('consumer-generator-files-table', 'data_previous')],
              [State('consumer-generator-files-table', 'data')],
              [State('consumer-generator-files-store', 'data')],
              prevent_initial_call=True)
def cg_show_removed_rows(previous, current, data):
    print(previous, current)
    previous_ids = [r['lfd_id'] for r in previous]
    current_ids = [r['lfd_id'] for r in current]
    removed_ids = list(set(previous_ids) - set(current_ids))
    print(removed_ids)

    if removed_ids is None:
        raise PreventUpdate
    else:
        # Remove the rows from the stored files
        data['all_components'] = [x for x in data['all_components'] if x['lfd_id'] not in removed_ids]

    return data


# Callback to handle file upload and addition
@app.callback(
    Output('consumer-generator-files-store', 'data'),
    Output('consumer-generator-files-table', 'data'),
    Output('consumer-generator-upload-data', 'contents'),  # To clear the upload component
    Output('consumer-generator-caption-input', 'value'),  # also clear the caption input
    Output('ts-temporal-scope-dropdown', 'value'),  # also clear the temporal scope dropdown
    Output('ts-consumer-generator-dropdown', 'value'),  # also clear the consumer/generator dropdown
    Output('ts-energy-type-dropdown', 'value'),  # also clear the energy type dropdown
    Output('consumer-generator-hydrogen-pressure-dropdown', 'value'),  # also clear the hydrogen pressure dropdown
    Output('consumer-generator-constant-power-input', 'value'),  # also clear the constant power input
    Input('consumer-generator-add-button', 'n_clicks'),
    State('consumer-generator-data-type-dropdown', 'value'),
    State('consumer-generator-upload-data', 'contents'),
    State('consumer-generator-upload-data', 'filename'),
    State('consumer-generator-caption-input', 'value'),
    State('ts-temporal-scope-dropdown', 'value'),
    State('ts-consumer-generator-dropdown', 'value'),
    State('ts-energy-type-dropdown', 'value'),
    State('consumer-generator-hydrogen-pressure-dropdown', 'value'),
    State('consumer-generator-constant-power-input', 'value'),
    State('consumer-generator-files-store', 'data'),
)
def cg_add_file(n_clicks, data_type_dropdown, contents, filename, caption, temporal_scope, consumer_or_generator,
             energy_type, hydrogen_pressure, const_val, data):
    if n_clicks is None:
        # prevent the None callbacks is important with the store component.
        # you don't want to update the store for nothing.
        raise PreventUpdate

    if not caption or not consumer_or_generator or not energy_type:
        raise PreventUpdate

    if (not hydrogen_pressure) and (energy_type == "hydrogen"):
        raise PreventUpdate

    if data_type_dropdown == 'constant_power':
        if not const_val:
            raise PreventUpdate

    elif data_type_dropdown == 'time_series':
        if not contents or not filename or not temporal_scope:
            raise PreventUpdate


    # todo evtl auch Fehlermeldung an den User, wenn nicht alle Felder ausgefüllt sind

    # Give a default data dict with 0 clicks if there's no data.
    data = data or {'all_components': []}

    # create a unique id for the row / file
    if len(data['all_components']) == 0:
        lfd_id = 1
    else:
        lfd_id = data['all_components'][-1]['lfd_id'] + 1

    data['all_components'].append({'lfd_id': lfd_id,
                                   'file_name': filename if data_type_dropdown == 'time_series' else '',
                                   'contents': contents if data_type_dropdown == 'time_series' else '',
                                   'caption': caption,
                                   'temporal_scope': temporal_scope if data_type_dropdown == 'time_series' else '',
                                   'type': consumer_or_generator,
                                   'energy_type': energy_type,
                                   'hydrogen_pressure': hydrogen_pressure if energy_type == 'hydrogen' else '',
                                   'power_value': const_val if data_type_dropdown == 'constant_power' else '',
                                   'data_type': data_type_dropdown})


    print(len(data['all_components']))

    # Update the table data
    table_data = [
        {
            'lfd_id': f['lfd_id'],
            'file_name': f['file_name'],
            'caption': f['caption'],
            'temporal_scope': f['temporal_scope'],
            'type': f['type'],
            'energy_type': f['energy_type'],
            'hydrogen_pressure': f['hydrogen_pressure'] if f['energy_type'] == 'hydrogen' else '',
            'power_value': f['power_value'] if f['data_type'] == 'constant_power' else '',
            'data_type': f['data_type'],
        }
        for f in data['all_components']
    ]

    print(data)

    return data, table_data, None, "", "", "", "", "", ""



# hide or show tank components
@app.callback(
    Output('photovoltaics-components-container', 'style'),
    [Input('hide-components-photovoltaics', 'value')]
)
def toggle_components_visibility_photovoltaics(hide_values):
    if 'hide' in hide_values:
        return {'display': 'none'}
    return {'display': 'block'}


# Callback for the reverse geocoding
@app.callback(
    Output("pv_geocode_address", "value"),
    Output("pv_geo_map", "figure"),
    Input("pv_button_reverse_geocode_and_update_map", "n_clicks"),
    State("pv_latitude", "value"),
    State("pv_longitude", "value")
)
def pv_reverse_geocode(n_clicks, latitude, longitude):
    #if n_clicks is None:
    #    raise PreventUpdate

    import geopy
    from geopy.geocoders import Nominatim

    geolocator = Nominatim(user_agent="h2pp-tuberlin-app-pv-geocoder")
    location = geolocator.reverse(f"{latitude}, {longitude}")

    if location is None:
        raise PreventUpdate

    # Get the map figure to show the location
    df = px.data.carshare()  # todo any way to doing the scatter plot without a dataframe?
    fig = px.scatter_mapbox(df, lat=[location.latitude], lon=[location.longitude], zoom=5, size=[5],
                            mapbox_style='open-street-map')

    return location.address, fig

# Callback to do the geocoding by first getting the location and then do reverse geocoding to get the address wellformatted back
# Reason is the problem with duplicate outputs in Dash, so this is a workaround
# this one first does geocoding, then triggers the reverse geocoding button
@app.callback(
    Output("pv_latitude", "value"),
    Output("pv_longitude", "value"),
    Output("pv_button_reverse_geocode_and_update_map", "n_clicks"),
    Input("pv_button_geocode", "n_clicks"),
    State("pv_geocode_address", "value"),
    State("pv_button_reverse_geocode_and_update_map", "n_clicks"),
)
def pv_geocode_and_reverse_geocode(n_clicks, address, n_clicks_reverse):
    if n_clicks is None:
        raise PreventUpdate

    if n_clicks_reverse is None:
        n_clicks_reverse = 0

    import geopy
    from geopy.geocoders import Nominatim

    geolocator = Nominatim(user_agent="h2pp-tuberlin-app-pv-geocoder")
    location = geolocator.geocode(address)

    if location is None:
        raise PreventUpdate

    return location.latitude, location.longitude, n_clicks_reverse + 1


# A callback that enables lat/long input fields and disables geocoding input field when the manual input checkbox is checked, and vice versa
# also the geocode button should be disabled when manual input is checked but the "update map" button should be enabled and vice versa
@app.callback(
    Output("pv_geocode_address", "disabled"),
    Output("pv_latitude", "disabled"),
    Output("pv_longitude", "disabled"),
    Output("pv_button_geocode", "disabled"),
    Output("pv_button_reverse_geocode_and_update_map", "disabled"),
    Input("pv_manual_lat_lon", "value"),
)
def pv_enable_manual_input_lat_long(checked):
    if "manual_input" in checked:
        return True, False, False, True, False
    else:
        return False, True, True, False, True



if __name__ == '__main__':
    app.run(debug=True)
