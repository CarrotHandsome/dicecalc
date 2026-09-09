import base64
import json

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ALL, MATCH, ctx, dcc, html
from dash.exceptions import PreventUpdate

from engine import Die, KeepIfHigherChance, roll_dice, roll_value, simulate_distribution


def make_die_row(index, count="1", faces=""):
    return html.Div(
        id={"type": "die-row", "index": index},
        className="die-row",
        children=[
            html.Label("Count:"),
            html.Button("-", id={"type": "die-count-minus", "index": index}, className="step-btn"),
            dcc.Input(
                id={"type": "die-count", "index": index},
                type="number",
                value=count,
                min=1,
                step=1,
                className="die-count-field",
            ),
            html.Button("+", id={"type": "die-count-plus", "index": index}, className="step-btn"),
            html.Label("Faces (comma-separated):"),
            dcc.Input(
                id={"type": "die-faces", "index": index},
                type="text",
                value=faces,
                className="die-faces-field",
            ),
            html.Button("Remove", id={"type": "die-remove", "index": index}),
        ],
    )


app = Dash(
    __name__,
    routes_pathname_prefix='/dicecalc/',
    requests_pathname_prefix='/dicecalc/'
)
app.title = "Dice Simulator"

app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("Dice Simulator"),

        dcc.Store(id="next-die-index", data=1),
        dcc.Download(id="download-settings"),

        html.Div(
            className="section",
            children=[
                html.H3("Dice"),
                html.Button("Add Die", id="add-die-btn", n_clicks=0),
                html.Div(id="dice-rows-container", children=[make_die_row(0)]),
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
                        dcc.Input(id="threshold-input", type="number", value=0.50, min=0, max=1, step=0.01),

                        html.Label("Rerolls:"),
                        dcc.Input(id="rerolls-input", type="number", value=2, min=0, step=1),

                        html.Label("Simulations:"),
                        dcc.Input(id="simulations-input", type="number", value=100000, min=1, step=1),

                        html.Label("Slots:"),
                        dcc.Input(id="slots-input", type="number", value=None, step=1, placeholder="all"),
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
    Output("slots-input", "value", allow_duplicate=True),
    Input("slots-input", "value"),
    prevent_initial_call=True,
)
def normalize_slots(current_value):
    # "Slots" defaults to "all" (None). Dash's built-in stepper/typing
    # handles the raw increment/decrement; this just catches the field
    # reaching 0 (via typing, or stepping down from 1) and treats that as
    # "back to all" rather than a literal zero.
    if current_value is not None and current_value <= 0:
        return None
    raise PreventUpdate


@app.callback(
    Output({"type": "die-count", "index": MATCH}, "value"),
    Input({"type": "die-count-minus", "index": MATCH}, "n_clicks"),
    Input({"type": "die-count-plus", "index": MATCH}, "n_clicks"),
    State({"type": "die-count", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def adjust_die_count(minus_clicks, plus_clicks, current_value):
    # Dash's built-in number-input stepper only works for plain string ids;
    # it breaks (clears the field) for pattern-matching ids like die-count's,
    # so this field gets its own explicit +/- buttons instead, with Dash's
    # broken native stepper hidden via CSS (see .die-row .dash-input-stepper).
    if not ctx.triggered_id or ctx.triggered[0]["value"] is None:
        raise PreventUpdate
    try:
        value = int(current_value)
    except (TypeError, ValueError):
        value = 1
    if ctx.triggered_id["type"] == "die-count-minus":
        return max(1, value - 1)
    return value + 1


@app.callback(
    Output("dice-rows-container", "children"),
    Output("next-die-index", "data"),
    Input("add-die-btn", "n_clicks"),
    State("dice-rows-container", "children"),
    State("next-die-index", "data"),
    prevent_initial_call=True,
)
def add_die(n_clicks, rows, next_index):
    # Appends a fresh row without touching the existing ones, so whatever a
    # user has already typed/stepped into other rows is left completely
    # alone rather than being regenerated from some stale snapshot.
    return rows + [make_die_row(next_index)], next_index + 1


@app.callback(
    Output("dice-rows-container", "children", allow_duplicate=True),
    Input({"type": "die-remove", "index": ALL}, "n_clicks"),
    State("dice-rows-container", "children"),
    prevent_initial_call=True,
)
def remove_die(_, rows):
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate
    # ALL-pattern callbacks also fire when a new matching component first
    # appears on the page (e.g. a die row was just added), not only on a
    # real click. Such spurious fires report n_clicks as None; only treat
    # this as an actual removal request when a real click value came in.
    if not ctx.triggered or ctx.triggered[0]["value"] is None:
        raise PreventUpdate
    return [row for row in rows if row["props"]["id"]["index"] != triggered["index"]]


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
    State("slots-input", "value"),
    prevent_initial_call=True,
)
def compute(roll_clicks, sim_clicks, counts, faces_list, threshold, rerolls, simulations, slots):
    dice = build_dice(counts, faces_list)
    if not dice:
        return "Add at least one die with faces.", go.Figure()

    rule = KeepIfHigherChance(threshold)

    if ctx.triggered_id == "roll-btn":
        roll_dice(dice, rule, rerolls)
        values = [die.value for die in dice]
        total = roll_value(dice, slots)
        fig = go.Figure(go.Bar(x=[f"Die {i + 1}" for i in range(len(values))], y=values))
        fig.update_layout(title="Roll Result", yaxis_title="Value")
        if slots is not None and slots < len(values):
            kept = sorted(values, reverse=True)[:slots]
            return f"Values: {values}  |  Kept ({slots} slots): {kept}  |  Total: {total}", fig
        return f"Values: {values}  |  Total: {total}", fig

    results = simulate_distribution(dice, rule, rerolls, simulations, slots)
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
    State("slots-input", "value"),
    prevent_initial_call=True,
)
def save_settings(n_clicks, counts, faces_list, threshold, rerolls, simulations, slots):
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
        "slots": slots,
    }
    return dcc.send_string(json.dumps(settings, indent=4), filename="dice_settings.json")


@app.callback(
    Output("dice-rows-container", "children", allow_duplicate=True),
    Output("next-die-index", "data", allow_duplicate=True),
    Output("threshold-input", "value"),
    Output("rerolls-input", "value"),
    Output("simulations-input", "value"),
    Output("slots-input", "value"),
    Input("load-upload", "contents"),
    prevent_initial_call=True,
)
def load_settings(contents):
    _, content_string = contents.split(",", 1)
    settings = json.loads(base64.b64decode(content_string))

    rows = [
        make_die_row(i, count=str(die["count"]), faces=", ".join(str(face) for face in die["faces"]))
        for i, die in enumerate(settings["dice"])
    ]

    return (
        rows,
        len(rows),
        settings["threshold"],
        settings["rerolls"],
        settings["simulations"],
        settings.get("slots"),
    )
