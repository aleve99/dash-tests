import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, Input, Output, dash_table
from dash_bootstrap_templates import load_figure_template
from json import load, dump, loads
from json.decoder import JSONDecodeError
from pandas import DataFrame
import plotly.express as px
from random import randint
from flask import request, jsonify
from pathlib import Path
from typing import Tuple, List, Dict
from datetime import datetime
from os import environ


DATA_DIR = Path("." if not environ.get("DATA_DIR") else environ['DATA_DIR'])
DATA = DATA_DIR.joinpath("data.json")

RANGES: List[str] = []

dbc_css = ("https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.2/dbc.min.css")
app = Dash(__name__, external_stylesheets=[dbc.themes.SLATE, dbc_css])
server = app.server

load_figure_template("slate")

def load_and_tabulate_data() -> Tuple[DataFrame , List[str]]:
    global RANGES
    if DATA.exists():
        with open(DATA) as file:
            data: dict = load(file)
            loans_data: Dict[Dict[str, List[dict]]] = data["LOANS"]
            symbols: dict = data["SYMBOLS"]
            timestamp = data["TIMESTAMP"]
    else:
        data: dict = {}
        loans_data: dict = {}
        symbols: dict = {}
        timestamp = 0

    RANGES = loans_data.keys()

    table_dict = {
        "range": [],
        "storage_address": [],
        "utilization_ratio": [],
        "total_collateral_usd": [],
        "total_borrow_usd": [],
        "loan_type": [],
        **{symbol + "_borrow_usd": [] for symbol in symbols.values()},
        **{symbol + "_collateral_usd": [] for symbol in symbols.values()}
    }

    for r, loans_by_range in loans_data.items():
        for loan_type, loans in loans_by_range.items():
            for loan in loans:
                table_dict['range'].append(r)
                table_dict['storage_address'].append(loan["escrowAddress"])
                table_dict['utilization_ratio'].append(int(loan["borrowUtilisationRatio"]) / 1e4)
                table_dict['total_collateral_usd'].append(int(loan["totalCollateralBalanceValue"]) / 1e4)
                table_dict['total_borrow_usd'].append(int(loan["totalBorrowBalanceValue"]) / 1e4)
                table_dict['loan_type'].append(loan_type)       
                for asset_id, symbol in symbols.items():
                    collaterals: list = loan['collaterals']
                    borrows: list = loan['borrows']
                    
                    collateral = list(filter(lambda c: c['assetId'] == int(asset_id), collaterals))
                    borrow = list(filter(lambda c: c['assetId'] == int(asset_id), borrows))

                    table_dict[symbol + "_collateral_usd"].append(
                        int(collateral[0]['balanceValue']) / 1e4 if len(collateral) != 0 else 0
                    )

                    table_dict[symbol + "_borrow_usd"].append(
                        int(borrow[0]['borrowBalanceValue']) / 1e4 if len(borrow) != 0 else 0
                    )
    
    return DataFrame(data=table_dict), symbols, datetime.fromtimestamp(timestamp)
load_and_tabulate_data()

@server.route("/update-jobs", methods=['PUT'])
def update_jobs():
    try:
        record = loads(request.data)
    except JSONDecodeError:
        return "Can't decode object", 500

    if record is not None:
        with open(DATA, 'w') as file:
            dump(record, file)
            
        server.logger.info(f"{DATA.absolute()} updated!")
        return jsonify({"response": "Jobs updated"})
    else:
        return "Can't decode object", 500

schema = [
    Output('borr-uti-graph', 'figure'),
    Output('table-div', 'children'),
    Output("update-time", "children")
]
schema.extend(
    Output(f"num-range-{i}", "children") for i in range(len(RANGES))
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
    df, symbols, timestamp = load_and_tabulate_data()

    totals = [len(df[df["range"] == r]) for r in RANGES]

    tot_borrow = df['total_borrow_usd'].sum()
    tot_collateral = df['total_collateral_usd'].sum()
    
    output = [px.scatter(
        data_frame=df,
        x="utilization_ratio",
        y="total_borrow_usd",
        custom_data=["storage_address"],
        title="Liquidation Bot Dashboard",
    ).update_traces(hovertemplate=None), dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{'id': c, 'name': c} for c in df.columns],
        id="accounts-table",
        sort_action="native",
        style_table={'overflowY': 'scroll'},
    ), html.Div(f"Last update: {timestamp}")]
    
    output.extend(
        dbc.Card([
            dbc.CardHeader(f"{tuple(int(n)/1e4 for n in r.split('_'))}", style={'font-weight': 'bold', 'font-size': '150%'}),
            dbc.CardBody([
                html.H1(n, className="card-title"),
                html.P("loans", className="card-text"),
            ])
        ]) for r, n in zip(RANGES, totals)
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
def change_lookup_address(click_data: str):
    df, symbols, timestamp = load_and_tabulate_data()

    if click_data == None:
        filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]
    else:
        filtered_data = df[df["storage_address"] == click_data["points"][0]["customdata"][-1]].to_dict("records")
        if not filtered_data:
            filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]

    first_row = {"TYPE": "collateral usd", **{symbol: filtered_data[0][symbol + "_collateral_usd"] for symbol in symbols.values()}}
    second_row = {"TYPE": "borrow usd", **{symbol: filtered_data[0][symbol + "_borrow_usd"] for symbol in symbols.values()}}
    
    return html.Div([
            html.H6(
                dcc.Markdown(f"""
                    Storage address: [{filtered_data[0]['storage_address'][:8]}...{filtered_data[0]['storage_address'][-8:]}](https://allo.info/account/{filtered_data[0]['storage_address']})

                    Utilization ratio: {filtered_data[0]['utilization_ratio']}

                    Total collateral: {filtered_data[0]['total_collateral_usd']}$
                    
                    Total borrow: {filtered_data[0]['total_borrow_usd']}$"""),
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
                        id=f"num-range-{i}",
                    )) for i, _ in enumerate(RANGES)
                ], style={"margin": "10px"}),
                dbc.Row([
                    dbc.Col(dbc.Card(
                        id="tot-borrow"
                    )),
                    dbc.Col(dbc.Card(
                        id="tot-collateral"
                    )),
                ], style={"margin": "10px"})
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
