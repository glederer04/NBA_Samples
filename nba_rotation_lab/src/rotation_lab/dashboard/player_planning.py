"""Coach-facing minute planning; explicit builds and immutable report snapshots."""

import json
from copy import deepcopy
from threading import Lock

import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dash_table, dcc, html, no_update

from rotation_lab.modeling.planner_evidence import candidate_pool, planner_evidence
from rotation_lab.modeling.planner_plan import plan_snapshot, validate_snapshot
from rotation_lab.modeling.player_planner import digest, solve_rotation, validate_request

_BUILD_LOCK = Lock()
COLORS = [
    "#2563eb",
    "#0891b2",
    "#7c3aed",
    "#d97706",
    "#059669",
    "#db2777",
    "#475569",
    "#9333ea",
    "#0e7490",
    "#a16207",
    "#be123c",
    "#4338ca",
]


def dropdown(id, options=None, value=None, **kwargs):
    return dcc.Dropdown(id="pp-" + id, options=options or [], value=value, **kwargs)


def field(label, child):
    return html.Div([html.Label(label, className="filter-label"), child], className="pp-field")


def table(id, columns, data=None, **kwargs):
    return dash_table.DataTable(
        id="pp-" + id,
        columns=columns,
        data=data or [],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#edf2f8",
            "color": "#334155",
            "fontWeight": "600",
            "whiteSpace": "normal",
        },
        style_cell={
            "fontFamily": "inherit",
            "fontSize": 13,
            "padding": "10px",
            "border": "none",
            "borderBottom": "1px solid #e2e8f0",
            "textAlign": "left",
            "color": "#17243a",
            "backgroundColor": "white",
            "minWidth": 65,
        },
        style_data_conditional=[
            {"if": {"column_id": "name"}, "minWidth": 150, "fontWeight": "600"}
        ],
        **kwargs,
    )


def layout(team="NYK", lineup=None):
    team = team if team in {"NYK", "SAS"} else "NYK"
    selected = []
    if lineup and lineup in planner_evidence(team)["keys"]:
        selected = lineup.split("-")
    return html.Div(
        [
            dcc.Store(id="pp-history", storage_type="local", data=[]),
            html.Div(
                [
                    html.Div("PLAYER-MINUTE PLANNING", className="eyebrow"),
                    html.H1("Build the rotation", className="page-title"),
                    html.P(
                        (
                            "Set the minutes. Shape the roles. See who shares the floor "
                            "across all four quarters."
                        ),
                        className="page-subtitle",
                    ),
                ]
            ),
            html.Div(
                [
                    field(
                        "Team",
                        dropdown(
                            "team",
                            [
                                {"label": "New York Knicks", "value": "NYK"},
                                {"label": "San Antonio Spurs", "value": "SAS"},
                            ],
                            team,
                            clearable=False,
                        ),
                    ),
                    field(
                        "Opponent context",
                        dropdown(
                            "opponent",
                            [{"label": "Average opponent", "value": "average"}],
                            "average",
                            clearable=False,
                        ),
                    ),
                    field(
                        "Venue",
                        dropdown(
                            "venue",
                            [
                                {"label": "Neutral / unspecified", "value": "neutral"},
                                {"label": "Home", "value": "home"},
                                {"label": "Away", "value": "away"},
                            ],
                            "neutral",
                            clearable=False,
                        ),
                    ),
                ],
                className="pp-grid",
            ),
            html.P(id="pp-sample", className="pp-note"),
            html.Section(
                [
                    html.H2("1 · Confirm availability"),
                    html.P(
                        (
                            "Choose 5–12 players from this historical roster. Selection is "
                            "your availability decision, not a live injury report."
                        ),
                        className="pp-note",
                    ),
                    dropdown(
                        "active",
                        value=selected,
                        multi=True,
                        placeholder="Choose the players available for this plan…",
                    ),
                    html.Button(
                        "Start with the 10 most-used players",
                        id="pp-seed",
                        disabled=True,
                        n_clicks=0,
                        className="button-secondary",
                    ),
                    html.H2("2 · Set player minutes"),
                    html.P(
                        (
                            "Edit a cell to set whole minutes. Targets are preferences; "
                            "minimums, maximums, stint limits and rest are enforced."
                        ),
                        className="pp-note",
                    ),
                    table(
                        "minutes",
                        [
                            {
                                "name": label,
                                "id": key,
                                "type": "numeric" if key != "name" else "text",
                                "editable": key != "name",
                            }
                            for key, label in [
                                ("name", "Player"),
                                ("min", "Min"),
                                ("target", "Target"),
                                ("max", "Max"),
                                ("stint", "Max stint"),
                                ("rest", "Min rest"),
                            ]
                        ],
                        editable=True,
                    ),
                    html.Div(id="pp-feasibility", role="status", className="pp-note"),
                    html.Details(
                        [
                            html.Summary("Opening five, closing five & role coverage"),
                            html.P(
                                (
                                    "Opening and closing selections are locks for the first "
                                    "and last minute. Assign roles yourself; a player may "
                                    "cover more than one."
                                ),
                                className="pp-note",
                            ),
                            html.Div(
                                [
                                    field(label, dropdown(key, multi=True))
                                    for key, label in [
                                        ("starters", "Must open"),
                                        ("closers", "Must close"),
                                        ("handler", "Ball handlers"),
                                        ("interior", "Interior defenders"),
                                        ("creator", "Shot creators"),
                                    ]
                                ],
                                className="pp-grid",
                            ),
                            dcc.Checklist(
                                id="pp-roles",
                                options=[
                                    {"label": " Always include a " + label, "value": key}
                                    for key, label in [
                                        ("handler", "handler"),
                                        ("interior", "interior defender"),
                                        ("creator", "creator"),
                                    ]
                                ],
                                value=[],
                                className="pp-checks",
                            ),
                        ],
                        className="pp-details",
                    ),
                    html.Details(
                        [
                            html.Summary("Pair rules, rest windows & locked stints"),
                            html.P(
                                (
                                    "Together: both in or both out. Apart: never share the "
                                    "floor. Stagger: at least one on court. Times are elapsed "
                                    "game minutes, 0–48."
                                ),
                                className="pp-note",
                            ),
                            table(
                                "pairs",
                                [
                                    {"name": "Player A", "id": "a", "presentation": "dropdown"},
                                    {"name": "Player B", "id": "b", "presentation": "dropdown"},
                                    {"name": "Rule", "id": "kind", "presentation": "dropdown"},
                                ],
                                editable=True,
                                row_deletable=True,
                            ),
                            html.Button(
                                "Add pair rule",
                                id="pp-add-pair",
                                n_clicks=0,
                                className="button-secondary",
                            ),
                            table(
                                "windows",
                                [
                                    {
                                        "name": "Resting player",
                                        "id": "player",
                                        "presentation": "dropdown",
                                    },
                                    {"name": "From minute", "id": "start", "type": "numeric"},
                                    {"name": "Until minute", "id": "end", "type": "numeric"},
                                ],
                                editable=True,
                                row_deletable=True,
                            ),
                            html.Button(
                                "Add rest window",
                                id="pp-add-window",
                                n_clicks=0,
                                className="button-secondary",
                            ),
                            html.H3("Locked lineup windows"),
                            html.P(
                                (
                                    "Select a stint in a built plan and lock it below. Delete "
                                    "a row here to unlock it."
                                ),
                                className="pp-note",
                            ),
                            table(
                                "locks",
                                [
                                    {"name": "Lineup", "id": "label", "editable": False},
                                    {"name": "From minute", "id": "start", "type": "numeric"},
                                    {"name": "Until minute", "id": "end", "type": "numeric"},
                                    {"name": "Key", "id": "key", "editable": False},
                                ],
                                editable=True,
                                row_deletable=True,
                                hidden_columns=["key"],
                            ),
                        ],
                        className="pp-details",
                    ),
                    html.Div(
                        [
                            field(
                                "Planning priority",
                                dropdown(
                                    "preset",
                                    [
                                        {"label": "Balanced", "value": "balanced"},
                                        {"label": "Fewer changes", "value": "continuity"},
                                        {"label": "Stronger evidence", "value": "evidence"},
                                    ],
                                    "balanced",
                                    clearable=False,
                                ),
                            ),
                            dcc.Checklist(
                                id="pp-unseen",
                                options=[
                                    {
                                        "label": " Allow unobserved five-player combinations",
                                        "value": "yes",
                                    }
                                ],
                                value=[],
                            ),
                        ],
                        className="pp-grid",
                    ),
                    html.P(
                        (
                            "Regulation only · one-minute substitution grid · quarter breaks "
                            "reset stint length and credit 2 / 15 / 2 minutes of rest. Live "
                            "substitutions depend on stoppages."
                        ),
                        className="pp-note",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Build rotation",
                                id="pp-build",
                                n_clicks=0,
                                className="button-primary",
                            ),
                            html.Button(
                                "Build a different rotation",
                                id="pp-alternative",
                                n_clicks=0,
                                className="button-secondary",
                            ),
                        ],
                        className="pp-actions",
                    ),
                    html.P(
                        "Builds run only when requested, with a 12-second solve limit. "
                        "Your hard limits are never relaxed.",
                        className="pp-note",
                    ),
                    dcc.Loading(html.Div(id="pp-status", role="status"), type="circle"),
                ],
                className="panel pp-editor",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("3 · Review the plan"),
                            field("Saved plans", dropdown("selected", clearable=False)),
                            html.Button(
                                "Restore this plan’s settings",
                                id="pp-restore",
                                disabled=True,
                                n_clicks=0,
                                className="button-secondary",
                            ),
                        ],
                        className="pp-review-head",
                    ),
                    html.Div(id="pp-stale", role="status"),
                    html.Div(id="pp-comparison"),
                    html.Div(id="pp-summary"),
                    field(
                        "Timeline color",
                        dropdown(
                            "color",
                            [
                                {"label": "Player identity", "value": "identity"},
                                {"label": "Lineup evidence", "value": "evidence"},
                                {"label": "Estimated lineup margin / 48", "value": "estimate"},
                            ],
                            "identity",
                            clearable=False,
                        ),
                    ),
                    html.Div(
                        dcc.Graph(id="pp-timeline", config={"displayModeBar": False}),
                        className="pp-timeline",
                    ),
                    html.P(id="pp-color-note", className="pp-note"),
                    html.Div(
                        [
                            field("Inspect a stint", dropdown("stint", clearable=False)),
                            html.Button(
                                "Lock this stint",
                                id="pp-lock",
                                n_clicks=0,
                                className="button-secondary",
                            ),
                        ],
                        className="pp-grid",
                    ),
                    html.Div(id="pp-stint-detail"),
                    html.Div(id="pp-compliance"),
                    html.Details(
                        [
                            html.Summary("Lineup evidence & estimation audit"),
                            html.Div(id="pp-evidence"),
                        ],
                        className="pp-details",
                    ),
                    html.Details(
                        [
                            html.Summary("What if a player’s cap changes?"),
                            html.P(
                                (
                                    "Change this player’s maximum or mark them unavailable, "
                                    "then rebuild. Minimum and target are lowered to the new "
                                    "cap only when you press this explicit action. Compare "
                                    "the new plan with the saved one."
                                ),
                                className="pp-note",
                            ),
                            html.Div(
                                [
                                    field("Player", dropdown("sensitivity-player")),
                                    field(
                                        "New maximum",
                                        dcc.Input(
                                            id="pp-cap",
                                            type="number",
                                            min=0,
                                            max=48,
                                            step=1,
                                            value=20,
                                        ),
                                    ),
                                    html.Button(
                                        "Apply cap to inputs",
                                        id="pp-apply-cap",
                                        n_clicks=0,
                                        className="button-secondary",
                                    ),
                                    html.Button(
                                        "Mark unavailable",
                                        id="pp-unavailable",
                                        n_clicks=0,
                                        className="button-secondary",
                                    ),
                                ],
                                className="pp-grid",
                            ),
                        ],
                        className="pp-details",
                    ),
                    html.Form(
                        [
                            dcc.Input(id="pp-pdf-data", name="plan", type="hidden", value=""),
                            html.Button(
                                "Download this saved plan · PDF",
                                id="pp-pdf-button",
                                type="submit",
                                disabled=True,
                                className="button-primary",
                            ),
                        ],
                        action="/reports/player-plan.pdf",
                        method="post",
                        target="_blank",
                    ),
                    html.P(
                        (
                            "The PDF uses this exact saved schedule and its evidence "
                            "snapshot. Saved plans stay in this browser; rebuilding uses the "
                            "current dataset."
                        ),
                        className="pp-note",
                    ),
                ],
                className="panel",
            ),
        ],
        className="page-content pp-page",
    )


def make_request(
    team,
    rows,
    opponent,
    venue,
    starters,
    closers,
    handlers,
    interiors,
    creators,
    roles,
    pairs,
    windows,
    locks,
    preset,
    unseen,
):
    players = deepcopy(rows or [])
    for p in players:
        for key, ids in [
            ("starter", starters),
            ("closer", closers),
            ("handler", handlers),
            ("interior", interiors),
            ("creator", creators),
        ]:
            p[key] = str(p["id"]) in (ids or [])
    return dict(
        team=team,
        players=players,
        opponent=opponent or "average",
        venue=venue or "neutral",
        roles=roles or [],
        pairs=[{"players": [p.get("a"), p.get("b")], "kind": p.get("kind")} for p in pairs or []],
        windows=windows or [],
        locks=[{k: p.get(k) for k in ("key", "start", "end")} for p in locks or []],
        preset=preset or "balanced",
        unseen=bool(unseen),
    )


REQUEST_FIELDS = [
    ("team", "value"),
    ("minutes", "data"),
    ("opponent", "value"),
    ("venue", "value"),
    ("starters", "value"),
    ("closers", "value"),
    ("handler", "value"),
    ("interior", "value"),
    ("creator", "value"),
    ("roles", "value"),
    ("pairs", "data"),
    ("windows", "data"),
    ("locks", "data"),
    ("preset", "value"),
    ("unseen", "value"),
]


@callback(
    Output("pp-active", "options"),
    Output("pp-opponent", "options"),
    Output("pp-sample", "children"),
    Output("pp-opponent", "disabled"),
    Output("pp-venue", "disabled"),
    Output("pp-seed", "disabled"),
    Output("pp-restore", "disabled"),
    Input("pp-team", "value"),
)
def load_roster(team):
    e = planner_evidence(team)
    note = (
        f"Season {str(e['season'])[-4:]}–{str(int(str(e['season'])[-4:]) + 1)[-2:]} · "
        f"{e['games']} validated games · {e['start']} to {e['end']}. "
    )
    note += (
        "Context blend passed both historical holdout baselines."
        if e["audit"]["use_context"]
        else (
            "Historical lineup estimates are used: the context blend did not outperform both "
            "baselines. Opponent and venue do not adjust this estimate."
        )
    )
    return (
        [{"label": p["name"], "value": p["id"]} for p in e["roster"]],
        [{"label": "Average opponent", "value": "average"}]
        + [{"label": o, "value": o} for o in e["opponents"]],
        note,
        not e["audit"]["use_context"],
        not e["audit"]["use_context"],
        False,
        False,
    )


@callback(
    Output("pp-active", "value"),
    Input("pp-seed", "n_clicks"),
    Input("pp-team", "value"),
    Input("pp-unavailable", "n_clicks"),
    State("pp-active", "value"),
    State("pp-sensitivity-player", "value"),
    prevent_initial_call=True,
)
def select_roster(seed, team, unavailable, active, player):
    if ctx.triggered_id == "pp-seed":
        return [p["id"] for p in planner_evidence(team)["roster"][:10]]
    if ctx.triggered_id == "pp-unavailable":
        return [p for p in active or [] if p != player]
    eligible = {p["id"] for p in planner_evidence(team)["roster"]}
    return active if active and set(active).issubset(eligible) else []


@callback(
    Output("pp-minutes", "data"),
    *[
        Output("pp-" + k, "options")
        for k in ["starters", "closers", "handler", "interior", "creator", "sensitivity-player"]
    ],
    Output("pp-pairs", "dropdown"),
    Output("pp-windows", "dropdown"),
    Input("pp-active", "value"),
    Input("pp-apply-cap", "n_clicks"),
    State("pp-minutes", "data"),
    State("pp-team", "value"),
    State("pp-sensitivity-player", "value"),
    State("pp-cap", "value"),
)
def edit_roster(active, cap_click, rows, team, player, cap):
    if not active:
        return [], *[[]] * 6, {}, {}
    roster = {p["id"]: p for p in planner_evidence(team)["roster"]}
    active = [p for p in active or [] if p in roster]
    existing = {str(p["id"]): p for p in rows or []}
    total = sum(roster[p]["minutes"] for p in active)
    targets = {p: round(240 * roster[p]["minutes"] / total) for p in active} if total else {}
    if targets:
        first = max(targets, key=targets.get)
        targets[first] += 240 - sum(targets.values())
    result = []
    for pid in active:
        target = min(48, targets[pid])
        p = deepcopy(
            existing.get(
                pid,
                dict(
                    id=pid,
                    name=roster[pid]["name"],
                    min=max(0, target - 6),
                    target=target,
                    max=min(48, target + 6),
                    stint=12,
                    rest=2,
                ),
            )
        )
        if (
            ctx.triggered_id == "pp-apply-cap"
            and pid == player
            and isinstance(cap, (int, float))
            and 0 <= cap <= 48
            and float(cap).is_integer()
        ):
            p.update(max=int(cap), min=min(p["min"], int(cap)), target=min(p["target"], int(cap)))
        result.append(p)
    options = [{"label": roster[p]["name"], "value": p} for p in active]
    pairs = {
        "a": {"options": options},
        "b": {"options": options},
        "kind": {
            "options": [{"label": k.title(), "value": k} for k in ["together", "apart", "stagger"]]
        },
    }
    return result, *[options] * 6, pairs, {"player": {"options": options}}


@callback(
    Output("pp-pairs", "data"),
    Input("pp-add-pair", "n_clicks"),
    State("pp-pairs", "data"),
    prevent_initial_call=True,
)
def add_pair(n, rows):
    return (rows or []) + [{"a": None, "b": None, "kind": "stagger"}]


@callback(
    Output("pp-windows", "data"),
    Input("pp-add-window", "n_clicks"),
    State("pp-windows", "data"),
    prevent_initial_call=True,
)
def add_window(n, rows):
    return (rows or []) + [{"player": None, "start": 0, "end": 4}]


def get_plan(history, selected):
    return next(
        (p for p in history or [] if p.get("id") == selected and not validate_snapshot(p)), None
    )


@callback(
    Output("pp-feasibility", "children"),
    Output("pp-stale", "children"),
    *[Input("pp-" + k, prop) for k, prop in REQUEST_FIELDS],
    Input("pp-selected", "value"),
    Input("pp-history", "data"),
)
def feasibility(*values):
    request = make_request(*values[:-2])
    selected, history = values[-2:]
    errors = validate_request(request)
    text = (
        " · ".join(errors)
        if errors
        else (
            f"Range capacity: "
            f"{sum(p['min'] for p in request['players'])}–"
            f"{sum(p['max'] for p in request['players'])} "
            f"player-minutes. 240 required. Timing and lineup feasibility checked on build."
        )
    )
    plan = get_plan(history, selected)
    stale = (
        html.P(
            (
                "Inputs differ from this saved plan. Build again to apply them; the timeline "
                "and PDF still show the saved version."
            ),
            className="pp-warning",
        )
        if plan and digest(request) != plan["request_id"]
        else ""
    )
    return text, stale


@callback(
    Output("pp-history", "data"),
    Output("pp-status", "children"),
    Input("pp-build", "n_clicks"),
    Input("pp-alternative", "n_clicks"),
    *[State("pp-" + k, prop) for k, prop in REQUEST_FIELDS],
    State("pp-history", "data"),
    State("pp-selected", "value"),
    prevent_initial_call=True,
    running=[
        (Output("pp-build", "disabled"), True, False),
        (Output("pp-alternative", "disabled"), True, False),
    ],
)
def build(n, alternative, *values):
    request = make_request(*values[:-2])
    history, selected = values[-2:]
    errors = validate_request(request)
    if errors:
        return no_update, html.Div([html.P(e) for e in errors], className="pp-warning")
    if not _BUILD_LOCK.acquire(blocking=False):
        return no_update, html.P(
            "Another plan is being built. Your inputs are preserved; try again in a few seconds.",
            className="pp-warning",
        )
    try:
        e = planner_evidence(request["team"])
        if not set(p["id"] for p in request["players"]).issubset(p["id"] for p in e["roster"]):
            return no_update, "Choose players from the selected team’s current historical snapshot."
        prior = get_plan(history, selected)
        previous = (
            prior["schedule"]
            if ctx.triggered_id == "pp-alternative"
            and prior
            and prior["request_id"] == digest(request)
            else None
        )
        if ctx.triggered_id == "pp-alternative" and previous is None:
            return (
                no_update,
                "Build these inputs first. Alternatives preserve exactly the same constraints.",
            )
        units = candidate_pool(e, request)
        result = solve_rotation(request, units, time_limit=12, previous=previous)
        if "schedule" not in result:
            return no_update, html.P(" ".join(result["messages"]), className="pp-warning")
        plan = plan_snapshot(request, units, result, e, prior)
        kept = [p for p in history or [] if not validate_snapshot(p)][-2:]
        return [*kept, plan], html.P(
            " ".join(result["messages"]) + f" Built in {result['seconds']:.1f}s.",
            className="pp-success",
        )
    except (ValueError, KeyError) as exc:
        return no_update, html.P(
            "Unable to build from these inputs: " + str(exc), className="pp-warning"
        )
    finally:
        _BUILD_LOCK.release()


@callback(
    Output("pp-selected", "options"), Output("pp-selected", "value"), Input("pp-history", "data")
)
def saved_options(history):
    plans = [p for p in history or [] if not validate_snapshot(p)]
    return [
        {
            ("label"): (
                f"{p['request']['team']} · {p['created'][11:19]} UTC · "
                f"{p['request']['preset']} · {p['mu']:+.1f} est. margin"
            ),
            "value": p["id"],
        }
        for p in plans
    ], plans[-1]["id"] if plans else None


def simple_table(headers, rows):
    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([html.Th(h) for h in headers])),
                html.Tbody([html.Tr([html.Td(v) for v in row]) for row in rows]),
            ],
            className="pp-table",
        ),
        className="pp-table-wrap",
    )


def exposure_minutes(value):
    return "<1" if 0 < value < 1 else f"{value:.0f}"


def names(plan, key, short=False):
    lookup = {p["id"]: p["name"] for p in plan["players"]}
    return " · ".join(
        (lookup[p].split()[0][0] + ". " + " ".join(lookup[p].split()[1:])) if short else lookup[p]
        for p in key.split("-")
    )


def timeline(plan, mode="identity"):
    fig = go.Figure()
    if not plan:
        fig.update_layout(
            height=180,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            paper_bgcolor="white",
            plot_bgcolor="white",
            annotations=[
                dict(
                    text="Build a rotation to see the 48-minute schedule.",
                    showarrow=False,
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                )
            ],
        )
        return fig
    units = {u["key"]: u for u in plan["units"]}
    for i, p in enumerate(plan["players"]):
        for j, s in enumerate(plan["segments"]):
            if p["id"] not in s["key"].split("-"):
                continue
            u = units[s["key"]]
            color = COLORS[i % len(COLORS)]
            if mode == "evidence":
                color = (
                    "#2563eb"
                    if u["minutes"] >= 100 and u["games"] >= 10
                    else "#94a3b8"
                    if u["minutes"]
                    else "#d97706"
                )
            elif mode == "estimate":
                color = u["mu"]
            fig.add_trace(
                go.Bar(
                    x=[s["end"] - s["start"]],
                    base=[s["start"]],
                    y=[p["name"]],
                    orientation="h",
                    width=0.64,
                    marker=dict(
                        color=color, **({"coloraxis": "coloraxis"} if mode == "estimate" else {})
                    ),
                    showlegend=False,
                    customdata=[[j]],
                    hovertemplate=(
                        f"<b>{p['name']}</b><br>Minute "
                        f"{s['start']}–{s['end']}<br>{names(plan, s['key'], True)}<br>Est. "
                        f"margin / 48: {u['mu']:+.1f}<br>Direct sample: "
                        f"{exposure_minutes(u['minutes'])} "
                        f"min · {u['games']} games<extra></extra>"
                    ),
                )
            )
    for j, s in enumerate(plan["segments"]):
        fig.add_trace(
            go.Bar(
                x=[s["end"] - s["start"]],
                base=[s["start"]],
                y=["Five on court"],
                orientation="h",
                width=0.25,
                marker_color="#334155" if j % 2 else "#94a3b8",
                showlegend=False,
                customdata=[[j]],
                hovertemplate=names(plan, s["key"], True) + "<extra></extra>",
            )
        )
    for t in [12, 24, 36]:
        fig.add_vline(x=t, line_color="#cbd5e1", line_dash="dot")
    fig.update_layout(
        barmode="overlay",
        height=110 + 35 * (len(plan["players"]) + 1),
        margin=dict(l=5, r=20, t=35, b=45),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#334155"),
        xaxis=dict(
            range=[0, 48],
            tickvals=[0, 6, 12, 18, 24, 30, 36, 42, 48],
            title="Elapsed game minutes",
            fixedrange=True,
        ),
        yaxis=dict(autorange="reversed", fixedrange=True),
        coloraxis=dict(
            colorscale=[[0, "#b45353"], [0.5, "#e2e8f0"], [1, "#16816d"]],
            cmin=-20,
            cmax=20,
            colorbar=dict(title="Est. / 48", thickness=10, len=0.6),
        ),
        annotations=[
            dict(x=t, y=1.09, xref="x", yref="paper", text=f"Q{i + 1}", showarrow=False)
            for i, t in enumerate([6, 18, 30, 42])
        ],
        clickmode="event+select",
    )
    return fig


@callback(
    Output("pp-summary", "children"),
    Output("pp-timeline", "figure"),
    Output("pp-color-note", "children"),
    Output("pp-stint", "options"),
    Output("pp-stint", "value"),
    Output("pp-compliance", "children"),
    Output("pp-evidence", "children"),
    Output("pp-pdf-data", "value"),
    Output("pp-pdf-button", "disabled"),
    Output("pp-comparison", "children"),
    Input("pp-selected", "value"),
    Input("pp-history", "data"),
    Input("pp-color", "value"),
)
def render_plan(selected, history, mode):
    plan = get_plan(history, selected)
    if not plan:
        return "", timeline(None), "", [], None, "", "", "", True, ""
    lo, hi = plan["interval"]
    summary = html.Div(
        [
            html.Div([html.Small(label), html.Strong(value)], className="pp-metric")
            for label, value in [
                ("Assigned minutes", "240 / 240"),
                ("Est. margin · 48 minutes", f"{plan['mu']:+.1f}"),
                ("95% estimate range", f"{lo:+.1f} to {hi:+.1f}"),
                ("Established lineup share", f"{plan['established']:.0f}%"),
            ]
        ],
        className="pp-metrics",
    )
    summary = html.Div(
        [
            summary,
            html.P(
                (
                    f"{plan['solver']['status'].title()} · {plan['substitutions']} player "
                    f"entries after tip-off · {plan['observed']:.0f}% in observed units. "
                )
                + (
                    "This is a historical estimate, not a predicted final score. The range "
                    "describes uncertainty in the estimate, not the range of possible game scores. "
                    "Established lineups have at least 100 shared minutes in 10 games."
                ),
                className="pp-note",
            ),
        ]
    )
    note = {
        ("identity"): (
            "Each player keeps one color; the thin bottom band separates lineup stints. "
            "Select a stint to inspect or lock its five players."
        ),
        ("evidence"): (
            "Blue: ≥100 minutes and ≥10 games. Gray: smaller direct sample. Amber: no direct "
            "sample."
        ),
        ("estimate"): (
            "Green: positive estimated lineup margin. Gray: near zero. Red: negative. These "
            "are estimates per 48 minutes, not historical stint +/−."
        ),
    }[mode]
    options = [
        {
            ("label"): (
                f"Q{s['start'] // 12 + 1} · {s['start']}–{s['end']} min · "
                f"{names(plan, s['key'], True)}"
            ),
            "value": j,
        }
        for j, s in enumerate(plan["segments"])
    ]
    compliance = html.Div(
        [
            html.H3("Minutes & constraints"),
            simple_table(
                ["Player", "Allowed", "Target", "Assigned", "Longest stint", "Status"],
                [
                    [
                        p["name"],
                        f"{p['min']}–{p['max']}",
                        p["target"],
                        p["assigned"],
                        f"{p['longest']} min",
                        p["binding"],
                    ]
                    for p in plan["players"]
                ],
            ),
            html.P(
                "Role coverage: "
                + " · ".join(
                    f"{role.title()} {minutes}/48 minutes"
                    for role, minutes in plan.get("role_minutes", {}).items()
                ),
                className="pp-note",
            )
            if plan.get("role_minutes")
            else None,
            html.P(
                (
                    "Every minute has five available players. All selected roles, pair rules, "
                    "rest windows and lineup locks passed independent validation."
                ),
                className="pp-note",
            ),
            simple_table(
                ["Pair rule", "Players", "Shared minutes"],
                [
                    [
                        p["kind"],
                        " + ".join(
                            next(r["name"] for r in plan["players"] if r["id"] == pid)
                            for pid in p["players"]
                        ),
                        p["together"],
                    ]
                    for p in plan["pairs"]
                ],
            )
            if plan["pairs"]
            else None,
        ]
    )
    evidence = html.Div(
        [
            simple_table(
                [
                    "Five-player unit",
                    "Planned",
                    "Direct sample",
                    "Est. / 48",
                    "95% range",
                    "Method",
                ],
                [
                    [
                        names(plan, u["key"], True),
                        plan["schedule"].count(u["key"]),
                        f"{exposure_minutes(u['minutes'])} min / {u['games']} G",
                        f"{u['mu']:+.1f}",
                        f"{u['interval'][0]:+.1f} to {u['interval'][1]:+.1f}",
                        u["method"],
                    ]
                    for u in plan["units"]
                ],
            ),
            html.P(
                (
                    "Observed units blend their scoring sample with 48 prior minutes. "
                    "Unobserved units have no direct sample. No individual on/off or "
                    "overlapping trio values are added together. Uncertainty resamples whole "
                    "games jointly across lineups (200 refits)."
                ),
                className="pp-note",
            ),
            html.P(audit_text(plan), className="pp-note"),
        ]
    )
    prior = plan.get("comparison")
    comparison = ""
    if prior:
        comparison = html.Div(
            [
                html.H3("Compared with the previous saved plan"),
                html.P(
                    (
                        f"Previous: {prior['created'][11:19]} UTC · Selected: "
                        f"{plan['created'][11:19]} UTC"
                    ),
                    className="pp-note",
                ),
                simple_table(
                    ["Metric", "Previous", "Selected", "Change"],
                    [
                        [
                            "Est. margin / 48",
                            f"{prior['mu']:+.1f}",
                            f"{plan['mu']:+.1f}",
                            f"{plan['mu'] - prior['mu']:+.1f}",
                        ],
                        [
                            "Established share",
                            f"{prior['established']:.0f}%",
                            f"{plan['established']:.0f}%",
                            f"{plan['established'] - prior['established']:+.0f} pp",
                        ],
                        [
                            "Player entries",
                            prior["substitutions"],
                            plan["substitutions"],
                            plan["substitutions"] - prior["substitutions"],
                        ],
                    ],
                ),
                html.P(
                    f"{prior['changed_minutes']} of 48 lineup minutes changed. "
                    + (
                        "Same constraints."
                        if prior["same_constraints"]
                        else (
                            "Different inputs. The player table below shows changes in "
                            "availability and assigned minutes."
                        )
                    ),
                    className="pp-note",
                ),
                simple_table(
                    ["Player", "Previous minutes", "Selected minutes", "Change"],
                    [
                        [
                            p["name"],
                            p["assigned"],
                            next((q["assigned"] for q in plan["players"] if q["id"] == p["id"]), 0),
                            next((q["assigned"] for q in plan["players"] if q["id"] == p["id"]), 0)
                            - p["assigned"],
                        ]
                        for p in prior["players"]
                    ],
                )
                if not prior["same_constraints"]
                else None,
            ]
        )
    return (
        summary,
        timeline(plan, mode),
        note,
        options,
        0,
        compliance,
        evidence,
        json.dumps(plan),
        False,
        comparison,
    )


def audit_text(plan):
    a = plan["audit"]
    if not a.get("available"):
        return a["reason"]
    return (
        (
            f"Solver: {plan['solver']['status']}; objective gap "
            f"{plan['solver'].get('gap')}. "
            f"Chronological audit: {a['train_games']} train / {a['tune_games']} tune / "
            f"{a['test_games']} later test games. Weighted interval RMSE (lower is better): "
            f"context blend {a['blended_error']:.2f}; team baseline "
            f"{a['baseline_error']:.2f}; existing lineup shrinkage {a['lineup_error']:.2f}. "
        )
        + (
            "Context blend enabled. "
            if a["use_context"]
            else "Context blend did not beat both baselines; team-prior lineup shrinkage used. "
        )
        + (
            "Context uses opponent identity, home court, period and prior score state; "
            "complete opponent lineups are unavailable. Planning assumes neutral score state "
            "and equal quarter weights. These observational estimates do not identify causal "
            "player impact."
        )
    )


@callback(
    Output("pp-stint-detail", "children"),
    Input("pp-stint", "value"),
    State("pp-selected", "value"),
    State("pp-history", "data"),
)
def stint_detail(index, selected, history):
    plan = get_plan(history, selected)
    if not plan or index is None or not 0 <= index < len(plan["segments"]):
        return ""
    s = plan["segments"][index]
    u = next(u for u in plan["units"] if u["key"] == s["key"])
    return html.Div(
        [
            html.H3(f"Minute {s['start']}–{s['end']} · {s['end'] - s['start']} minutes"),
            html.P(names(plan, s["key"]), className="pp-lineup-names"),
            html.P(
                (
                    f"{u['method']} · {exposure_minutes(u['minutes'])} direct minutes in "
                    f"{u['games']} "
                    f"games · estimated margin / 48 {u['mu']:+.1f}."
                ),
                className="pp-note",
            ),
        ],
        className="pp-stint-card",
    )


@callback(
    Output("pp-stint", "value", allow_duplicate=True),
    Input("pp-timeline", "clickData"),
    prevent_initial_call=True,
)
def select_stint(click):
    return click["points"][0]["customdata"][0] if click else no_update


@callback(
    Output("pp-locks", "data"),
    Input("pp-lock", "n_clicks"),
    State("pp-stint", "value"),
    State("pp-selected", "value"),
    State("pp-history", "data"),
    State("pp-locks", "data"),
    prevent_initial_call=True,
)
def lock_stint(n, index, selected, history, locks):
    plan = get_plan(history, selected)
    if not plan or index is None:
        return no_update
    s = plan["segments"][index]
    lock = {**s, "label": names(plan, s["key"], True)}
    return (
        (locks or [])
        if any(all(r.get(k) == s[k] for k in ["key", "start", "end"]) for r in locks or [])
        else [*(locks or []), lock]
    )


@callback(
    *[Output("pp-" + k, prop, allow_duplicate=True) for k, prop in REQUEST_FIELDS[1:]],
    Output("pp-active", "value", allow_duplicate=True),
    Output("pp-status", "children", allow_duplicate=True),
    Input("pp-restore", "n_clicks"),
    State("pp-selected", "value"),
    State("pp-history", "data"),
    State("pp-team", "value"),
    prevent_initial_call=True,
)
def restore(n, selected, history, team):
    plan = get_plan(history, selected)
    if not plan or plan["request"]["team"] != team:
        return *[no_update] * 15, "Select the saved plan’s team before restoring its settings."
    r = plan["request"]
    players = deepcopy(r["players"])
    roles = [
        [p["id"] for p in players if p.get(k)]
        for k in ["starter", "closer", "handler", "interior", "creator"]
    ]
    pairs = [dict(a=p["players"][0], b=p["players"][1], kind=p["kind"]) for p in r["pairs"]]
    locks = [{**s, "label": names(plan, s["key"], True)} for s in r["locks"]]
    return (
        players,
        r["opponent"],
        r["venue"],
        *roles,
        r["roles"],
        pairs,
        r["windows"],
        locks,
        r["preset"],
        ["yes"] if r["unseen"] else [],
        [p["id"] for p in players],
        "Saved constraints restored. Rebuild only if you want a new schedule.",
    )


@callback(
    *[
        Output("pp-" + key, "value", allow_duplicate=True)
        for key in ["starters", "closers", "handler", "interior", "creator", "roles"]
    ],
    *[Output("pp-" + key, "data", allow_duplicate=True) for key in ["pairs", "windows", "locks"]],
    Input("pp-team", "value"),
    prevent_initial_call=True,
)
def reset_team_constraints(team):
    return tuple([] for _ in range(9))
