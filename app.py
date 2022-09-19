from dash import Dash, html, dcc, Input, Output, dash_table
from dash_bootstrap_components import themes
from dash_bootstrap_templates import load_figure_template
from json import load, dump
from pandas import DataFrame
import plotly.express as px, plotly.io as pio
from random import randint

PATH = "jobs.json"

dbc_css = ("https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.2/dbc.min.css")
app = Dash(__name__, external_stylesheets=[themes.SLATE, dbc_css])
load_figure_template("slate")

df, symbols = DataFrame(), None

def load_and_tabulate_data():
    global symbols
    with open(PATH, "r") as file:
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

    return DataFrame(data=table_dict)

def main():
    global df
    df = load_and_tabulate_data()

    app.layout = html.Div([
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
                        data=df.to_dict("records"),
                        columns=[{'id': c, 'name': c} for c in df.columns],
                        id="accounts-table",
                        sort_action="native",
                        style_table={'overflowY': 'scroll'},
                    )
                ], className="dbc", id="table-div")
            ])
        ], className="dbc"),
        dcc.Interval(
            id='interval-component',
            interval=10*1000, # in milliseconds
            n_intervals=0
        )
    ], className="dbc")

@app.callback(
    Output('borr-uti-graph', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_graph(n):
    df = load_and_tabulate_data()
    return px.scatter(
        data_frame=df,
        x="utilization_ratio",
        y="total_borrow_usd",
        range_x=[0.91,1],
        range_y=[0,20000],
        custom_data=["storage_address"],
        title="Liquidation Bot Dashboard"
    ).update_traces(hovertemplate=None)

@app.callback(
    Output('table-div', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_table(n):
    df = load_and_tabulate_data()
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{'id': c, 'name': c} for c in df.columns],
        id="accounts-table",
        sort_action="native",
        style_table={'overflowY': 'scroll'},
    )

@app.callback(
    Output("details-div", "children"),
    Input("borr-uti-graph", "clickData")
)
def change_lookup_address(click_data: str):
    if click_data == None:
        filtered_data = [df.to_dict("records")[randint(0, len(df.to_dict("records")) - 1)]]
    else:
        filtered_data = df[df["storage_address"] == click_data["points"][0]["customdata"][-1]].to_dict("records")
    
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

if __name__ == '__main__':
    main()
    app.run(debug=True)
