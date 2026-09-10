import base64
import json

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ALL, MATCH, ctx, dcc, html
from dash.exceptions import PreventUpdate

from engine import Die, KeepIfHigherChance, roll_dice, roll_value, simulate_distribution

PLOTLY_FONT = "Public Sans, sans-serif"
PLOTLY_ACCENT = "#d1a35c"
PLOTLY_TEXT = "#f0e9dc"
PLOTLY_GRID = "#3a332a"


def themed_layout(**overrides):
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=PLOTLY_FONT, color=PLOTLY_TEXT, size=13),
        margin=dict(l=48, r=16, t=40, b=40),
        xaxis=dict(gridcolor=PLOTLY_GRID, zerolinecolor=PLOTLY_GRID),
        yaxis=dict(gridcolor=PLOTLY_GRID, zerolinecolor=PLOTLY_GRID),
    )
    layout.update(overrides)
    return layout


def stat_field(label, input_component):
    # Relies entirely on Dash's own built-in number-input stepper (which
    # works correctly for plain string ids), just styled to match the app.
    return html.Div(
        className="stat-field",
        children=[
            html.Label(label, className="stat-label"),
            input_component,
        ],
    )


def die_count_field(index, count):
    # Dash's built-in stepper is broken for pattern-matching ids (it clears
    # the field instead of stepping), so this one field gets its own
    # explicit +/- buttons instead, with the native one hidden via CSS.
    return html.Div(
        className="stat-field",
        children=[
            html.Label("Count", className="stat-label"),
            html.Div(
                className="stat-control",
                children=[
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
                ],
            ),
        ],
    )


def make_die_row(index, count="1", faces=""):
    return html.Div(
        id={"type": "die-row", "index": index},
        className="die-card",
        children=[
            die_count_field(index, count),
            html.Div(
                className="stat-field faces-field",
                children=[
                    html.Label("Faces (comma-separated)", className="stat-label"),
                    dcc.Input(
                        id={"type": "die-faces", "index": index},
                        type="text",
                        value=faces,
                        placeholder="1, 2, 3, 4, 5, 6",
                        className="die-faces-field mono-field",
                    ),
                ],
            ),
            html.Button("Remove", id={"type": "die-remove", "index": index}, className="btn btn-danger btn-remove"),
        ],
    )


app = Dash(
    __name__,
    routes_pathname_prefix='/dicecalc/',
    requests_pathname_prefix='/dicecalc/'
)
app.title = "Dice Simulator"

app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

app.layout = html.Div(
    className="app-container",
    children=[
        html.Header(
            className="app-header",
            children=[
                html.H1("Dice Simulator"),
                html.P("Roll, reroll, and simulate custom dice pools.", className="subtitle"),
            ],
        ),

        dcc.Store(id="next-die-index", data=1),
        dcc.Download(id="download-settings"),

        html.Div(
            className="panel",
            children=[
                html.Div(
                    className="panel-header",
                    children=[
                        html.H2("Dice"),
                        html.Button("Add Die", id="add-die-btn", n_clicks=0, className="btn btn-secondary"),
                    ],
                ),
                html.Div(id="dice-rows-container", className="die-list", children=[make_die_row(0)]),
            ],
        ),

        html.Div(
            className="panel",
            children=[
                html.H2("Rule Settings"),
                html.Div(
                    className="stat-grid",
                    children=[
                        stat_field(
                            "Threshold",
                            dcc.Input(id="threshold-input", type="number", value=0.50, min=0, max=1, step=0.01, className="mono-field"),
                        ),
                        stat_field(
                            "Rerolls",
                            # max is set purely to route around a bug in Dash's own
                            # stepper (it NaNs the field when min is set without max).
                            dcc.Input(id="rerolls-input", type="number", value=2, min=0, max=1000000, step=1, className="mono-field"),
                        ),
                        stat_field(
                            "Simulations",
                            dcc.Input(id="simulations-input", type="number", value=100000, min=1, max=100000000, step=1, className="mono-field"),
                        ),
                        stat_field(
                            "Slots",
                            dcc.Input(id="slots-input", type="number", value=None, step=1, placeholder="all", className="mono-field"),
                        ),
                    ],
                ),
            ],
        ),

        html.Div(
            className="panel action-row",
            children=[
                html.Button("Roll Once", id="roll-btn", n_clicks=0, className="btn btn-primary"),
                html.Button("Run Simulation", id="sim-btn", n_clicks=0, className="btn btn-primary"),
                dcc.Input(
                    id="save-name-input",
                    type="text",
                    value="dice_settings",
                    placeholder="save name",
                    className="mono-field save-name-input",
                ),
                html.Button("Save Settings", id="save-btn", n_clicks=0, className="btn btn-secondary"),
                dcc.Upload(
                    id="load-upload",
                    children=html.Button("Load Settings", className="btn btn-secondary"),
                    multiple=False,
                    style={},
                ),
            ],
        ),

        html.Div(
            className="panel",
            children=[
                html.H2("Results"),
                html.Div(id="results-text", className="results-summary mono-field"),
                dcc.Graph(
                    id="results-graph",
                    figure=go.Figure(layout=themed_layout()),
                    config={"displayModeBar": False, "responsive": True},
                ),
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
    # broken native stepper hidden via CSS (see .die-count-field .dash-input-stepper).
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
        return "Add at least one die with faces.", go.Figure(layout=themed_layout())

    rule = KeepIfHigherChance(threshold)

    if ctx.triggered_id == "roll-btn":
        roll_dice(dice, rule, rerolls)
        values = [die.value for die in dice]
        total = roll_value(dice, slots)
        fig = go.Figure(
            go.Bar(x=[f"Die {i + 1}" for i in range(len(values))], y=values, marker_color=PLOTLY_ACCENT),
            layout=themed_layout(title="Roll Result", yaxis_title="Value"),
        )
        if slots is not None and slots < len(values):
            kept = sorted(values, reverse=True)[:slots]
            return f"Values: {values}  |  Kept ({slots} slots): {kept}  |  Total: {total}", fig
        return f"Values: {values}  |  Total: {total}", fig

    results = simulate_distribution(dice, rule, rerolls, simulations, slots)
    avg = sum(results) / len(results)
    fig = go.Figure(
        go.Histogram(x=results, marker_color=PLOTLY_ACCENT),
        layout=themed_layout(title="Simulation Results", xaxis_title="Total", yaxis_title="Frequency"),
    )
    return f"Average total over {simulations} simulations: {avg:.3f}", fig


def sanitize_filename(name):
    name = "".join(c for c in (name or "") if c.isalnum() or c in (" ", "_", "-")).strip()
    name = name or "dice_settings"
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


@app.callback(
    Output("download-settings", "data"),
    Input("save-btn", "n_clicks"),
    State({"type": "die-count", "index": ALL}, "value"),
    State({"type": "die-faces", "index": ALL}, "value"),
    State("threshold-input", "value"),
    State("rerolls-input", "value"),
    State("simulations-input", "value"),
    State("slots-input", "value"),
    State("save-name-input", "value"),
    prevent_initial_call=True,
)
def save_settings(n_clicks, counts, faces_list, threshold, rerolls, simulations, slots, save_name):
    # Save exactly what's currently on screen, one entry per die row - even
    # a row with blank faces - rather than silently dropping incomplete
    # rows, which previously produced a "dice": [] file with no warning.
    settings = {
        "dice": [
            {
                "count": int(count) if count else 1,
                "faces": [int(value.strip()) for value in (faces_str or "").split(",") if value.strip()],
            }
            for count, faces_str in zip(counts, faces_list)
        ],
        "threshold": threshold,
        "rerolls": rerolls,
        "simulations": simulations,
        "slots": slots,
    }
    return dcc.send_string(json.dumps(settings, indent=4), filename=sanitize_filename(save_name))


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

    dice = settings["dice"] or [{"count": 1, "faces": []}]
    rows = [
        make_die_row(i, count=str(die["count"]), faces=", ".join(str(face) for face in die["faces"]))
        for i, die in enumerate(dice)
    ]

    return (
        rows,
        len(rows),
        settings["threshold"],
        settings["rerolls"],
        settings["simulations"],
        settings.get("slots"),
    )
