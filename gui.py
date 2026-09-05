import base64
import json

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ALL, ctx, dcc, html
from dash.exceptions import PreventUpdate

from engine import Die, KeepIfHigherChance, roll_dice, simulate_distribution

app = Dash(__name__)
app.title = "Dice Simulator"

app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("Dice Simulator"),

        dcc.Store(id="die-indices", data=[0]),
        dcc.Store(id="next-die-index", data=1),
        dcc.Store(id="die-defaults", data={"0": {"count": "1", "faces": ""}}),
        dcc.Download(id="download-settings"),

        html.Div(
            className="section",
            children=[
                html.H3("Dice"),
                html.Button("Add Die", id="add-die-btn", n_clicks=0),
                html.Div(id="dice-rows-container"),
            ],
        ),

        html.Div(
            className="section",
            children=[
                html.H3("Rule Settings"),
                html.Div(
                    className="field-row",
                    children=[
                        html.Label("Threshold:"),
                        dcc.Input(id="threshold-input", type="number", value=0.50, step=0.01),
                        html.Label("Rerolls:"),
                        dcc.Input(id="rerolls-input", type="number", value=2, step=1),
                        html.Label("Simulations:"),
                        dcc.Input(id="simulations-input", type="number", value=100000, step=1),
                    ],
                ),
            ],
        ),

        html.Div(
            className="section button-row",
            children=[
                html.Button("Roll Once", id="roll-btn", n_clicks=0),
                html.Button("Run Simulation", id="sim-btn", n_clicks=0),
                html.Button("Save Settings", id="save-btn", n_clicks=0),
                dcc.Upload(
                    id="load-upload",
                    children=html.Button("Load Settings"),
                    multiple=False,
                ),
            ],
        ),

        html.Div(
            className="section",
            children=[
                html.H3("Results"),
                html.Div(id="results-text"),
                dcc.Graph(id="results-graph"),
            ],
        ),
    ],
)


def build_dice(counts, faces_list):
    dice = []
    for count, faces_str in zip(counts, faces_list):
        if not count or not faces_str:
            continue
        faces = [int(value.strip()) for value in faces_str.split(",") if value.strip()]
        for _ in range(int(count)):
            dice.append(Die(faces))
    return dice


@app.callback(
    Output("dice-rows-container", "children"),
    Input("die-indices", "data"),
    State("die-defaults", "data"),
)
def render_dice_rows(indices, defaults):
    rows = []
    for index in indices:
        default = defaults.get(str(index), {"count": "1", "faces": ""})
        rows.append(
            html.Div(
                className="die-row",
                children=[
                    html.Label("Count:"),
                    dcc.Input(
                        id={"type": "die-count", "index": index},
                        type="number",
                        value=default["count"],
                        min=1,
                        step=1,
                    ),
                    html.Label("Faces (comma-separated):"),
                    dcc.Input(
                        id={"type": "die-faces", "index": index},
                        type="text",
                        value=default["faces"],
                    ),
                    html.Button("Remove", id={"type": "die-remove", "index": index}),
                ],
            )
        )
    return rows


@app.callback(
    Output("die-indices", "data"),
    Output("next-die-index", "data"),
    Output("die-defaults", "data"),
    Input("add-die-btn", "n_clicks"),
    State("die-indices", "data"),
    State("next-die-index", "data"),
    State("die-defaults", "data"),
    prevent_initial_call=True,
)
def add_die(n_clicks, indices, next_index, defaults):
    defaults = dict(defaults)
    defaults[str(next_index)] = {"count": "1", "faces": ""}
    return indices + [next_index], next_index + 1, defaults


@app.callback(
    Output("die-indices", "data", allow_duplicate=True),
    Input({"type": "die-remove", "index": ALL}, "n_clicks"),
    State("die-indices", "data"),
    prevent_initial_call=True,
)
def remove_die(_, indices):
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate
    # Any callback with an ALL-pattern dependency is treated as "multi" by
    # Dash, so even this single logical Output must be tuple-wrapped.
    return ([index for index in indices if index != triggered["index"]],)


@app.callback(
    Output("results-text", "children"),
    Output("results-graph", "figure"),
    Input("roll-btn", "n_clicks"),
    Input("sim-btn", "n_clicks"),
    State({"type": "die-count", "index": ALL}, "value"),
    State({"type": "die-faces", "index": ALL}, "value"),
    State("threshold-input", "value"),
    State("rerolls-input", "value"),
    State("simulations-input", "value"),
    prevent_initial_call=True,
)
def compute(roll_clicks, sim_clicks, counts, faces_list, threshold, rerolls, simulations):
    dice = build_dice(counts, faces_list)
    if not dice:
        return "Add at least one die with faces.", go.Figure()

    rule = KeepIfHigherChance(threshold)

    if ctx.triggered_id == "roll-btn":
        roll_dice(dice, rule, rerolls)
        values = [die.value for die in dice]
        fig = go.Figure(go.Bar(x=[f"Die {i + 1}" for i in range(len(values))], y=values))
        fig.update_layout(title="Roll Result", yaxis_title="Value")
        return f"Values: {values}  |  Total: {sum(values)}", fig

    results = simulate_distribution(dice, rule, rerolls, simulations)
    avg = sum(results) / len(results)
    fig = go.Figure(go.Histogram(x=results))
    fig.update_layout(title="Simulation Results", xaxis_title="Total", yaxis_title="Frequency")
    return f"Average total over {simulations} simulations: {avg:.3f}", fig


@app.callback(
    Output("download-settings", "data"),
    Input("save-btn", "n_clicks"),
    State({"type": "die-count", "index": ALL}, "value"),
    State({"type": "die-faces", "index": ALL}, "value"),
    State("threshold-input", "value"),
    State("rerolls-input", "value"),
    State("simulations-input", "value"),
    prevent_initial_call=True,
)
def save_settings(n_clicks, counts, faces_list, threshold, rerolls, simulations):
    settings = {
        "dice": [
            {
                "count": int(count),
                "faces": [int(value.strip()) for value in faces_str.split(",") if value.strip()],
            }
            for count, faces_str in zip(counts, faces_list)
            if count and faces_str
        ],
        "threshold": threshold,
        "rerolls": rerolls,
        "simulations": simulations,
    }
    # Same ALL-pattern "multi" wrapping requirement as remove_die above.
    return (dcc.send_string(json.dumps(settings, indent=4), filename="dice_settings.json"),)


@app.callback(
    Output("die-indices", "data", allow_duplicate=True),
    Output("next-die-index", "data", allow_duplicate=True),
    Output("die-defaults", "data", allow_duplicate=True),
    Output("threshold-input", "value"),
    Output("rerolls-input", "value"),
    Output("simulations-input", "value"),
    Input("load-upload", "contents"),
    prevent_initial_call=True,
)
def load_settings(contents):
    _, content_string = contents.split(",", 1)
    settings = json.loads(base64.b64decode(content_string))

    defaults = {
        str(i): {
            "count": die["count"],
            "faces": ", ".join(str(face) for face in die["faces"]),
        }
        for i, die in enumerate(settings["dice"])
    }
    indices = list(range(len(settings["dice"])))

    return (
        indices,
        len(indices),
        defaults,
        settings["threshold"],
        settings["rerolls"],
        settings["simulations"],
    )
