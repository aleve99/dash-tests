import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, Input, Output, dash_table
from dash_bootstrap_templates import load_figure_template
from json import dump, loads
from json.decoder import JSONDecodeError
import plotly.express as px
from random import randint
from flask import request, jsonify
from pathlib import Path
from os import environ
from payload import Payload


DATA_DIR = Path("." if not environ.get("DATA_DIR") else environ['DATA_DIR'])
DATA = DATA_DIR.joinpath("data.json")

dbc_css = ("https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.2/dbc.min.css")
app = Dash(__name__, external_stylesheets=[dbc.themes.SLATE, dbc_css])
server = app.server

load_figure_template("slate")

payload = Payload()
payload.read_json(DATA)
payload.compute_table()

@server.route("/update-jobs", methods=['PUT'])
def update_jobs():
    try:
        record = loads(request.data)
    except JSONDecodeError:
        server.logger.error(f"Error in decoding data: {request.data}")
        return "Can't decode object", 500

    if record is not None:
        with open(DATA, 'w') as file:
            dump(record, file)
            
        server.logger.info(f"{DATA.absolute()} updated!")
        return jsonify({"response": "Jobs updated"})
    else:
        server.logger.error(f"Error in decoding data: {request.data}")
        return "Can't decode object", 500

schema = [
    Output('borr-uti-graph', 'figure'),
    Output('table-div', 'children'),
    Output("update-time", "children")
]
schema.extend(
    Output(f"num-range-{i}-count", "children") for i in range(payload.n_ranges)
)
schema.extend(
    Output(f"num-range-{i}-runtime", "children") for i in range(payload.n_ranges)
)
schema.extend([
    Output("tot-borrow", "children"),
    Output("tot-collateral", "children")
])
schema.append(
    Input('refresh-btn', 'n_clicks')
)

@app.callback(schema)
def update_graph(n_clicks: int):
    payload.read_json(DATA)
    payload.compute_table()

    df = payload.df

    totals = [len(df[df["range"] == r]) for r in payload.ranges]

    tot_borrow = df['total_borrow_usd'].sum()
    tot_collateral = df['total_collateral_usd'].sum()
    
    light_df = df.drop("range", axis=1)
    output = [
        px.scatter(
            data_frame=df[["utilization_ratio", "total_borrow_usd", "storage_address"]],
            x="utilization_ratio",
            y="total_borrow_usd",
            custom_data=["storage_address"],
            title="Liquidation Bot Dashboard",
        ).update_traces(hovertemplate=None),
        dash_table.DataTable(
            data=light_df.to_dict("records"),
            columns=[{'id': c, 'name': c} for c in light_df.columns],
            id="accounts-table",
            sort_action="native",
            style_table={'overflowY': 'scroll'},
        ),
        html.Div(f"Last update: {payload.timestamp}")]
    

    output.extend(
        dbc.Card([
            dbc.CardHeader(f"{tuple(int(n)/1e4 for n in r.split('_'))}", style={'font-weight': 'bold', 'font-size': '150%'}),
            dbc.CardBody([
                html.H1(n, className="card-title"),
                html.P("loans", className="card-text"),
            ])
        ]) for r, n in zip(payload.ranges, totals)
    )
    
    output.extend(
        dbc.Card([
            dbc.CardHeader(f"{tuple(int(n)/1e4 for n in r.split('_'))}", style={'font-weight': 'bold', 'font-size': '150%'}),
            dbc.CardBody([
                html.H1(f"{int(payload.runtimes[r])}ms", className="card-title"),
                html.P("rolling runtime", className="card-text"),
            ])
        ]) for r in payload.ranges
    )

    output.extend([
        dbc.Card([
            dbc.CardHeader("Borrow", style={'font-weight': 'bold', 'font-size': '150%'}),
            dbc.CardBody([
                html.H1(f"{tot_borrow:,.2f}$", className="card-title"),
            ])
        ]),
        dbc.Card([
            dbc.CardHeader("Collateral", style={'font-weight': 'bold', 'font-size': '150%'}),
            dbc.CardBody([
                html.H1(f"{tot_collateral:,.2f}$", className="card-title"),
            ])
        ]),
    ])

    return output

@app.callback(
    Output("details-div", "children"),
    Input("borr-uti-graph", "clickData"),
)
def change_lookup_address(click_data: 'str | None'):
    payload.read_json(DATA)
    payload.compute_table()

    df = payload.df
    symbols = payload.symbols

    if click_data == None and df.empty:
        storage_address, ut_ratio, total_b, total_c = "", 0, 0, 0
    elif click_data == None and not df.empty:
        filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]
        
        storage_address = filtered_data[0]['storage_address']
        ut_ratio = filtered_data[0]['utilization_ratio']
        total_b = filtered_data[0]['total_borrow_usd']
        total_c = filtered_data[0]['total_collateral_usd']
    else:
        filtered_data = df[df["storage_address"] == click_data["points"][0]["customdata"][-1]].to_dict("records")
        if not filtered_data:
            filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]
        
        storage_address = filtered_data[0]['storage_address']
        ut_ratio = filtered_data[0]['utilization_ratio']
        total_b = filtered_data[0]['total_borrow_usd']
        total_c = filtered_data[0]['total_collateral_usd']
        

    first_row = {"TYPE": "collateral usd", **{symbol: filtered_data[0][symbol + "_collateral_usd"] for symbol in symbols.values()}}
    second_row = {"TYPE": "borrow usd", **{symbol: filtered_data[0][symbol + "_borrow_usd"] for symbol in symbols.values()}}
    
    return html.Div([
            html.H6(
                dcc.Markdown(f"""
                    Storage address: [{storage_address[:8]}...{storage_address[-8:]}](https://allo.info/account/{storage_address})

                    Utilization ratio: {ut_ratio}

                    Total collateral: {total_c}$
                    
                    Total borrow: {total_b}$"""),
            ),
            html.Br(),
            dash_table.DataTable(
                data=[first_row, second_row],
                columns=[{'id': c, 'name': c} for c in first_row.keys()],
                style_cell={'textAlign': 'center'},
                style_cell_conditional=[{"if": {"column_id": "TYPE"}, "textAlign": "left"}],
                id="details-table",
                style_table={'overflowY': 'scroll'}
            )
        ])

app.layout = html.Div([
    dbc.Row([
        dbc.Col(
            html.Div("", id="update-time", className='dbc'),
            width='auto',
        ),
        dbc.Col(
            html.Button("Refresh", id='refresh-btn', className="dbc"),
            width='auto'
        ),
    ], className="dbc", style={'padding': 10}, justify='center'),
    dcc.Tabs([
        dcc.Tab(label="Totals", className="dbc", children=[
            html.Div([
                dbc.Row([
                    dbc.Col(dbc.Card(
                        id=f"num-range-{i}-count",
                    )) for i, _ in enumerate(payload.ranges)
                ], style={"margin": "10px"}),
                dbc.Row([
                    dbc.Col(dbc.Card(
                        id=f"num-range-{i}-runtime",
                    )) for i, _ in enumerate(payload.ranges)
                ], style={"margin": "10px"}),
                dbc.Row([
                    dbc.Col(dbc.Card(
                        id="tot-borrow"
                    )),
                    dbc.Col(dbc.Card(
                        id="tot-collateral"
                    )),
                ], style={"margin-top": "20px", "margin-left": "10px", "margin-right": "10px"})
            ], style={'text-align': 'center', 'margin-top': "20px"})
        ]),
        dcc.Tab(label="Graph", className="dbc", children=[
            dcc.Graph(
                id="borr-uti-graph",
            ),
            html.Div(
                id="details-div",
                className="dbc"
            )
        ]),
        dcc.Tab(label="Table", className="dbc", children=[
            html.Div([
                dash_table.DataTable(
                    id="accounts-table",
                    sort_action="native",
                    style_table={'overflowY': 'scroll'},
                )
            ], className="dbc", id="table-div")
        ]),
    ], className="dbc"),
    #dcc.Interval(
    #    id='interval-component',
    #    interval=10*1000, # in milliseconds
    #    n_intervals=0
    #)
], className="dbc", style={"margin-left": "15px", "margin-right": "15px"})

if __name__ == '__main__':
    app.run(debug=True)
