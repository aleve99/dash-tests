from dash import Dash, html, dcc, Input, Output
from json import load
from os.path import expanduser
from pandas import DataFrame
import plotly.express as px

PATH = "jobs.json"

app = Dash(__name__)

def main():
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

    df = DataFrame(data=table_dict)

    fig = px.scatter(df, x="utilization_ratio", y="total_borrow_usd", title="Liquidation Bot Dashboard")

    app.layout = html.Div([
        dcc.Graph(
            id="borr-uti-graph",
            figure=fig
        )
    ])


if __name__ == '__main__':
    main()
    app.run(debug=True)
