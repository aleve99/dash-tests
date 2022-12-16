from dash import Dash, html, dcc, Input, Output, dash_table
from dash_bootstrap_components import themes
from dash_bootstrap_templates import load_figure_template
from json import load, dump, loads
from json.decoder import JSONDecodeError
from pandas import DataFrame
import plotly.express as px
from random import randint
from flask import request, jsonify
from pathlib import Path
from typing import Tuple, List

SUPPORTED_VERSIONS = (1,2)
BASE_FOLDER = Path(".")
JOBS_V1 = BASE_FOLDER.joinpath("jobs_V1.json")
JOBS_V2 = BASE_FOLDER.joinpath("jobs_V2.json")

dbc_css = ("https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.2/dbc.min.css")
app = Dash(__name__, external_stylesheets=[themes.SLATE, dbc_css])
server = app.server

load_figure_template("slate")

def load_and_tabulate_data(version: int) -> Tuple[DataFrame , List[str]]:   
    with open(JOBS_V1 if version == "V1" else JOBS_V2, "r") as file:
        jobs = [job for worker in load(file) for job in worker['jobs']]

    symbols = [key for key in jobs[0].keys() if key != "info"]

    table_dict = {
        "storage_address": [],
        "utilization_ratio": [],
        "total_collateral_usd": [],
        "total_borrow_usd": [],
        **{symbol + "_borrow_usd": [] for symbol in symbols},
        **{symbol + "_collateral_usd": [] for symbol in symbols}
    }

    for job in jobs:
        for key, value in job.items():
            if key == "info":
                table_dict['storage_address'].append(value["storage_address"])
                table_dict['utilization_ratio'].append(value["utilization_ratio"])
                table_dict['total_collateral_usd'].append(value["total_collateral_usd"])
                table_dict['total_borrow_usd'].append(value["total_borrow_usd"])
            else:
                table_dict[key + "_borrow_usd"].append(value["borrow_usd"])
                table_dict[key + "_collateral_usd"].append(value["active_collateral_usd"])
    
    return DataFrame(data=table_dict), symbols

@server.route("/update-jobs", methods=['PUT'])
def update_jobs():
    try:
        version = int(request.args['version'])
        if version not in SUPPORTED_VERSIONS:
            raise ValueError
    except (KeyError, ValueError):
        return "Must specify a supported version within request parameters: version: int, 1 | 2"
    
    try:
        record = loads(request.data)
    except JSONDecodeError:
        return "Can't decode object", 500

    if record is not None:
        with open(JOBS_V1 if version == 1 else JOBS_V2, 'w') as file:
            dump(record, file)
            
        server.logger.info(f"{JOBS_V1 if version == 1 else JOBS_V2} updated!")
        return jsonify({"response": "Jobs updated"})
    else:
        return "Can't decode object", 500

@app.callback(
    Output('borr-uti-graph', 'figure'),
    Input('version', 'value')
)
def update_graph(version: str):
    df = load_and_tabulate_data(version)[0]
    
    return px.scatter(
        data_frame=df,
        x="utilization_ratio",
        y="total_borrow_usd",
        custom_data=["storage_address"],
        title="Liquidation Bot Dashboard",
    ).update_traces(hovertemplate=None)

@app.callback(
    Output('table-div', 'children'),
    Input('version', 'value')
)
def update_table(version: str):
    df = load_and_tabulate_data(version)[0]
    
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{'id': c, 'name': c} for c in df.columns],
        id="accounts-table",
        sort_action="native",
        style_table={'overflowY': 'scroll'},
    )

@app.callback(
    Output("details-div", "children"),
    Input("borr-uti-graph", "clickData"),
    Input('version', 'value')
)
def change_lookup_address(click_data: str, version: str):
    df, symbols = load_and_tabulate_data(version)

    if click_data == None:
        filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]
    else:
        filtered_data = df[df["storage_address"] == click_data["points"][0]["customdata"][-1]].to_dict("records")
        if not filtered_data:
            filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]

    first_row = {"TYPE": "collateral usd", **{symbol: filtered_data[0][symbol + "_collateral_usd"] for symbol in symbols}}
    second_row = {"TYPE": "borrow usd", **{symbol: filtered_data[0][symbol + "_borrow_usd"] for symbol in symbols}}
    
    return html.Div([
            html.H6(
                dcc.Markdown(f"""
                    Storage address: [{filtered_data[0]['storage_address'][:8]}...{filtered_data[0]['storage_address'][-8:]}](https://algoexplorer.io/address/{filtered_data[0]['storage_address']})

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
    dcc.RadioItems(['V1', 'V2'], "V1", id="version", className="dbc"),
    dcc.Tabs([
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
        ])
    ], className="dbc"),
    #dcc.Interval(
    #    id='interval-component',
    #    interval=10*1000, # in milliseconds
    #    n_intervals=0
    #)
], className="dbc")

if __name__ == '__main__':
    app.run(debug=True)
