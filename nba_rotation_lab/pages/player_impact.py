"""Player on/off and matched player comparisons, without causal claims."""

import math

from dash import Input, Output, State, callback, dcc, html, register_page

from rotation_lab.dashboard.components import get_team_options
from rotation_lab.dashboard.impact import (
    filter_sample,
    summarize,
    team_dataset,
)
from rotation_lab.dashboard.impact_components import (
    comparison_card,
    coverage_note,
    interval_text,
    margin_chart,
    number,
    sample_line,
    split_table,
    table,
)

register_page(
    __name__, path="/player-impact", name="Player Impact", title="Player Impact | NBA Rotation Lab"
)


def field(label, component):
    return html.Div([html.Label(label, htmlFor=component.id, className="filter-label"), component])


def layout(team=None, player=None, **kwargs):
    teams = get_team_options()
    valid = [item["value"] for item in teams]
    selected = team if team in valid else "NYK" if "NYK" in valid else valid[0] if valid else None
    if team not in valid and player and str(player).isdigit():
        selected = next(
            (
                candidate
                for candidate in valid
                if int(player) in team_dataset(candidate)["players"].player_id.values
            ),
            selected,
        )
    return html.Div(
        [
            dcc.Store(id="impact-link", data=player),
            html.Div("PLAYER CONTEXT", className="eyebrow"),
            html.H1("Player Impact", className="page-title"),
            html.P(
                "How the team performs during a player's minutes—and during their rest.",
                className="page-subtitle",
            ),
            html.Div(
                [
                    field(
                        "TEAM",
                        dcc.Dropdown(
                            id="impact-team", options=teams, value=selected, clearable=False
                        ),
                    ),
                    field("PLAYER", dcc.Dropdown(id="impact-player", clearable=False)),
                    field("SEASON", dcc.Dropdown(id="impact-season", clearable=False)),
                    field(
                        "DATE RANGE",
                        dcc.DatePickerRange(id="impact-dates", display_format="MMM D, YYYY"),
                    ),
                ],
                className="panel impact-filters",
            ),
            html.Div(
                [
                    field(
                        "GAME UNIVERSE",
                        dcc.Dropdown(
                            id="impact-universe",
                            clearable=False,
                            value="appearances",
                            options=[
                                {"label": "Games this player appeared in", "value": "appearances"},
                                {
                                    "label": "All covered team games (includes absences)",
                                    "value": "all",
                                },
                            ],
                        ),
                    ),
                    field(
                        "DATA QUALITY",
                        dcc.Dropdown(
                            id="impact-quality",
                            clearable=False,
                            value="validated",
                            options=[
                                {"label": "Fully validated games", "value": "validated"},
                                {
                                    "label": "All valid five-player intervals (may be partial)",
                                    "value": "partial",
                                },
                            ],
                        ),
                    ),
                    html.Details(
                        [
                            html.Summary("Scoring sensitivity & method"),
                            dcc.Checklist(
                                id="impact-boundary",
                                options=[
                                    {
                                        "label": " Exclude intervals with boundary points",
                                        "value": "exclude",
                                    }
                                ],
                                value=[],
                            ),
                            html.P(
                                "The default preserves the existing (start, end] scoring rule. "
                                "This check removes whole flagged intervals from both samples. "
                                "It does not reassign points. Invalid lineups are always excluded. "
                                "Garbage time is included; no hidden adjustment is applied.",
                                className="impact-note",
                            ),
                        ],
                        className="impact-method",
                    ),
                ],
                className="panel impact-options",
            ),
            dcc.Loading(html.Div(id="impact-summary"), type="circle", delay_show=200),
            html.Div(
                [
                    html.Div("SIDE BY SIDE", className="section-eyebrow"),
                    html.H2("Compare two players", className="section-title"),
                    html.P(
                        "Compare the selected player with a teammate. This section uses "
                        "games where both appeared, within your season, dates and quality filters. "
                        "The single-player game-universe setting does not change this comparison.",
                        className="impact-note",
                    ),
                    field("COMPARE WITH", dcc.Dropdown(id="impact-compare", clearable=False)),
                    dcc.Loading(html.Div(id="impact-comparison"), type="circle", delay_show=200),
                ],
                className="panel",
            ),
            html.Details(
                [
                    html.Summary("How to read this analysis"),
                    html.P(
                        "Margin / 48 = 48 × (team points − opponent points) / minutes. "
                        "Swing = on-court rate − off-court rate. Higher margin and scoring are "
                        "favorable; lower opponent scoring is favorable. These are time-normalized "
                        "team outcomes, not possession net ratings or individual scoring stats."
                    ),
                    html.P(
                        "95% intervals resample whole games 2,000 times, keeping on/off "
                        "observations together. Each side needs 100 minutes across 10 games "
                        "before its interval is shown. A swing needs both sides. These "
                        "thresholds don't guarantee reliability. Narrower intervals do not "
                        "remove teammate, opponent, role or game-state confounding."
                    ),
                    html.P(
                        "For two players, the same bootstrap games are used for both players "
                        "and their swing difference. No overall winner is assigned. A favorable "
                        "rate doesn't prove superior ability. Possessions and adjusted "
                        "plus-minus are not available until those models are separately validated."
                    ),
                ],
                className="panel impact-method",
            ),
        ],
        className="page-content",
    )


@callback(
    Output("impact-player", "options"),
    Output("impact-player", "value"),
    Output("impact-season", "options"),
    Output("impact-season", "value"),
    Output("impact-dates", "start_date"),
    Output("impact-dates", "end_date"),
    Input("impact-team", "value"),
    State("impact-link", "data"),
)
def options(team, requested):
    if not team:
        return [], None, [], None, None, None
    data = team_dataset(team)
    players = [
        {"label": row.player_name, "value": int(row.player_id)}
        for row in data["players"].itertuples()
    ]
    seasons = sorted(data["games"].season_id.astype(str).unique(), reverse=True)
    season_types = data["games"].groupby("season_id").season_type.first().to_dict()
    season_options = [
        {
            "label": f"{s[-4:]}–{int(s[-4:]) + 1} · {season_types[s]}",
            "value": s,
        }
        for s in seasons
    ]
    try:
        requested = int(requested)
    except (TypeError, ValueError):
        requested = None
    chosen = (
        requested
        if requested in [p["value"] for p in players]
        else players[0]["value"]
        if players
        else None
    )
    games = data["games"]
    return (
        players,
        chosen,
        [{"label": "All covered seasons", "value": "all"}, *season_options],
        seasons[0] if seasons else "all",
        str(games.game_date.min().date()) if len(games) else None,
        str(games.game_date.max().date()) if len(games) else None,
    )


@callback(
    Output("impact-compare", "options"),
    Output("impact-compare", "value"),
    Input("impact-team", "value"),
    Input("impact-player", "value"),
    State("impact-compare", "value"),
)
def compare_options(team, player, current):
    if not team:
        return [], None
    players = [
        {"label": row.player_name, "value": int(row.player_id)}
        for row in team_dataset(team)["players"].itertuples()
        if row.player_id != player
    ]
    return players, current if current in [p["value"] for p in players] else players[0][
        "value"
    ] if players else None


FILTER_INPUTS = [
    Input("impact-team", "value"),
    Input("impact-player", "value"),
    Input("impact-season", "value"),
    Input("impact-dates", "start_date"),
    Input("impact-dates", "end_date"),
    Input("impact-quality", "value"),
    Input("impact-boundary", "value"),
]


def name_of(data, player):
    names = data["players"].set_index("player_id").player_name
    return str(names.get(player, "Player"))


@callback(Output("impact-summary", "children"), *FILTER_INPUTS, Input("impact-universe", "value"))
def single_player(team, player, season, start, end, quality, boundary, universe):
    if not team or not player:
        return html.P("Select a player.")
    data = team_dataset(team)
    intervals, meta = filter_sample(
        data, [player], season, start, end, universe, quality, "exclude" in (boundary or [])
    )
    if intervals.empty:
        return html.Div(
            [
                html.H2("No qualifying minutes"),
                html.P("Adjust the dates or quality filter to inspect another sample."),
                coverage_note(meta),
            ],
            className="panel",
        )
    result = summarize(intervals, player)
    swing = result["swing"][0]
    if math.isfinite(swing):
        direction = "higher" if swing >= 0 else "lower"
        interpretation = (
            f"The team's margin was {abs(swing):.1f} points per 48 {direction} "
            f"with {name_of(data, player)} on court than off court."
        )
    else:
        interpretation = "A swing cannot be calculated without minutes on both sides."
    ci = result["ci"][2]
    uncertainty = (
        "The swing interval includes zero; the direction is uncertain in this sample."
        if ci and ci[0][0] <= 0 <= ci[1][0]
        else "The swing interval excludes zero; context can still explain the difference."
        if ci
        else "Small sample: a swing interval needs 100 minutes and 10 games on each side."
    )
    return html.Div(
        [
            html.Div(
                [
                    html.Div("ON COURT / OFF COURT", className="section-eyebrow"),
                    html.H2(name_of(data, player), className="section-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        "ON/OFF SWING · MARGIN / 48", className="filter-label"
                                    ),
                                    html.Strong(number(swing, True), className="impact-swing"),
                                    html.Div(
                                        f"95% interval: {interval_text(ci)}",
                                        className="impact-note",
                                    ),
                                ]
                            ),
                            margin_chart(result),
                        ],
                        className="impact-hero",
                    ),
                    html.P(sample_line(result), className="impact-sample"),
                    html.P(interpretation),
                    html.P(uncertainty, className="impact-note"),
                    split_table(result),
                    coverage_note(meta),
                ],
                className="panel",
            ),
            html.Details(
                [
                    html.Summary("Teammates, opponents & scoring coverage"),
                    context_details(data, intervals, player),
                    html.P(
                        f"{meta['boundary_points']} combined points occur at interval ends. "
                        f"Sensitivity exclusions: {meta['boundary_excluded_minutes']:.1f} minutes. "
                        "Scoring corrections follow the existing scoring-event deltas. "
                        "Coverage percentages include excluded game time in the denominator.",
                        className="impact-note",
                    ),
                ],
                className="panel impact-method",
            ),
        ]
    )


def context_details(data, intervals, player):
    on_mask = intervals.players.map(lambda ids: player in ids)
    rows = []
    for teammate in data["players"].itertuples():
        if teammate.player_id == player:
            continue
        present = intervals.players.map(lambda ids, p=teammate.player_id: p in ids)
        shared = float(intervals.loc[present & on_mask, "duration_seconds"].sum()) / 60
        off = float(intervals.loc[present & ~on_mask, "duration_seconds"].sum()) / 60
        if shared or off:
            rows.append([teammate.player_name, shared, off])
    rows.sort(key=lambda row: -row[1])
    opponent_rows = []
    for opponent, sample in intervals.groupby("opponent_team_abbreviation"):
        result = summarize(sample, player, bootstrap=False)
        opponent_rows.append(
            [
                opponent,
                sample.game_id.nunique(),
                number(result["totals"][0][0] / 60),
                number(result["totals"][1][0] / 60),
                number(result["swing"][0], True),
            ]
        )
    return html.Div(
        [
            html.H3("Teammate overlap", className="impact-subtitle"),
            html.P(
                "Minutes with each teammate in the on and off groups. These overlapping rows "
                "are context, not additional independent samples.",
                className="impact-note",
            ),
            table(
                ["Teammate", "With selected player · min", "Without selected player · min"],
                [[row[0], number(row[1]), number(row[2])] for row in rows],
            ),
            html.H3("Opponent context", className="impact-subtitle"),
            table(["Opponent", "Games", "On min", "Off min", "Swing / 48"], opponent_rows),
        ]
    )


@callback(Output("impact-comparison", "children"), *FILTER_INPUTS, Input("impact-compare", "value"))
def compare_players(team, player, season, start, end, quality, boundary, other):
    if not team or not player or not other or player == other:
        return html.P("Choose two different players.", className="impact-note")
    data = team_dataset(team)
    intervals, meta = filter_sample(
        data,
        [player, other],
        season,
        start,
        end,
        "appearances",
        quality,
        "exclude" in (boundary or []),
    )
    if intervals.empty:
        return html.Div(
            [html.P("No shared appearance games match these filters."), coverage_note(meta)]
        )
    a, b = summarize(intervals, player), summarize(intervals, other)
    names = [name_of(data, p) for p in [player, other]]
    together = intervals.players.map(lambda ids: player in ids and other in ids)
    return html.Div(
        [
            comparison_card(a, b, names),
            html.Details(
                [
                    html.Summary("Full on/off splits"),
                    html.Div(
                        [
                            html.Div(
                                [html.H3(name, className="impact-subtitle"), split_table(result)]
                            )
                            for name, result in zip(names, [a, b], strict=True)
                        ],
                        className="impact-compare-grid",
                    ),
                ],
                className="impact-method",
            ),
            html.P(
                "An interval crossing zero means the apparent edge is uncertain. Even an interval "
                "on one side of zero is descriptive: players share minutes, and their off-court "
                "lineups and roles differ. These numbers do not identify a better player overall.",
                className="impact-note",
            ),
            html.P(
                f"Together: {intervals.loc[together, 'duration_seconds'].sum() / 60:,.1f} minutes. "
                "Shared minutes contribute to both players' on-court samples.",
                className="impact-sample",
            ),
            coverage_note(meta),
        ]
    )
