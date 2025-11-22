import dash
from dash import dcc, html
import plotly.graph_objs as go
from pymongo import MongoClient
import pandas as pd

# Mongo connection
client = MongoClient("mongodb://localhost:27017")
db = client["adaptive_cold_storage"]
col = db["events"]

def load_data(limit=500):
    """Fetch last N events from Mongo into a pandas DataFrame."""
    cursor = col.find().sort("ts", -1).limit(limit)
    docs = list(cursor)
    if not docs:
        return pd.DataFrame()

    # Normalize nested structure
    df = pd.json_normalize(docs)
    # Convert ts to datetime
    df["ts"] = pd.to_datetime(df["ts"])
    # Sort ascending
    df = df.sort_values("ts")
    return df

# Initialize Dash
app = dash.Dash(__name__)
app.title = "Adaptive Cold Storage Plots"

def make_figure(df, ycols, title, ylabel):
    traces = []
    for col in ycols:
        if col in df:
            traces.append(go.Scatter(x=df["ts"], y=df[col], mode="lines+markers", name=col))
    return {
        "data": traces,
        "layout": go.Layout(
            title=title,
            xaxis={"title": "Time"},
            yaxis={"title": ylabel},
            margin={"l":40, "r":20, "t":40, "b":40},
            hovermode="x unified",
        )
    }

app.layout = html.Div([
    html.H1("Adaptive Cold Storage — Data Plots"),
    dcc.Interval(id="refresh", interval=120000, n_intervals=0),  # auto-refresh every 5s

    dcc.Graph(id="temp"),
    dcc.Graph(id="humidity"),
    dcc.Graph(id="co2"),
    dcc.Graph(id="ethylene"),
    dcc.Graph(id="weight"),
    dcc.Graph(id="actuators"),
])

@app.callback(
    [
        dash.Output("temp", "figure"),
        dash.Output("humidity", "figure"),
        dash.Output("co2", "figure"),
        dash.Output("ethylene", "figure"),
        dash.Output("weight", "figure"),
        dash.Output("actuators", "figure"),
    ],
    [dash.Input("refresh", "n_intervals")]
)
def update_figs(n):
    df = load_data(limit=500)
    if df.empty:
        return [{}]*6

    fig_temp = make_figure(df,
        ["sensors.tray1.temp", "sensors.tray2.temp"],
        "Tray Temperatures", "°C")

    fig_hum = make_figure(df,
        ["sensors.tray1.humidity", "sensors.tray2.humidity"],
        "Tray Humidity", "%")

    fig_co2 = make_figure(df,
        ["sensors.tray1.co2ppm", "sensors.tray2.co2ppm"],
        "Tray CO₂", "ppm")

    fig_eth = make_figure(df,
        ["sensors.tray1.ethyleneppm", "sensors.tray2.ethyleneppm"],
        "Tray Ethylene", "ppm")

    fig_weight = make_figure(df,
        ["sensors.tray1.weight", "sensors.tray2.weight"],
        "Tray Weight", "g")

    fig_act = make_figure(df,
        ["decision.actuators.rackACvalve",
         "decision.actuators.rackHumidifiervalve",
         "decision.actuators.tray1fanspeed",
         "decision.actuators.tray2fanspeed"],
        "Actuator Outputs", "Value")

    return fig_temp, fig_hum, fig_co2, fig_eth, fig_weight, fig_act

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=True)
