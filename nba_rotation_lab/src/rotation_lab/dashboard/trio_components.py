"""Focused coach-facing trio exploration and five-player completion evidence."""

import math

from dash import Input, Output, State, callback, dcc, html, no_update

from rotation_lab.dashboard.components import compact_lineup_names, metric_card, player_headshot
from rotation_lab.dashboard.data import get_team_players
from rotation_lab.dashboard.impact_components import coverage_note, number, table
from rotation_lab.dashboard.trios import filter_trios, raw_confidence, trio_analysis, trio_detail


def control(label, component):
    return html.Div([html.Label(label, htmlFor=component.id, className="filter-label"), component])


def trio_layout():
    return html.Div(
        [
            html.Div(
                [
                    html.H2("Find a three-player core", className="section-title"),
                    html.P(
                        "Three teammates sharing the court while the other two spots can change. "
                        "Start with the most-used groups, then inspect who completed each core. "
                        "Required players above must be members of the trio.",
                        className="impact-note",
                    ),
                    html.Div(
                        [
                            control(
                                "EXCLUDE TRIO MEMBERS",
                                dcc.Dropdown(
                                    id="trio-excluded",
                                    multi=True,
                                    value=[],
                                    placeholder="Players not in the core",
                                ),
                            ),
                            control(
                                "MINIMUM TOGETHER MINUTES",
                                dcc.Input(
                                    id="trio-minutes",
                                    type="number",
                                    min=0,
                                    step=25,
                                    value=100,
                                    debounce=0.3,
                                    className="minutes-input",
                                ),
                            ),
                            control(
                                "MINIMUM GAMES",
                                dcc.Input(
                                    id="trio-games",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=10,
                                    debounce=0.3,
                                    className="minutes-input",
                                ),
                            ),
                            control(
                                "DATE RANGE · OPTIONAL",
                                dcc.DatePickerRange(
                                    id="trio-dates", display_format="MMM D, YYYY", clearable=True
                                ),
                            ),
                        ],
                        className="trio-filters",
                    ),
                    html.P(
                        "Exclusions apply to trio membership, not the other two lineup spots. "
                        "Defaults: 100 minutes and 10 games. Lower them to expose smaller samples.",
                        className="impact-note",
                    ),
                ],
                className="panel",
            ),
            html.Div(
                [
                    html.H2("How your regular cores performed", className="section-title"),
                    html.P(
                        "Compare the most-used matching cores. The dot shows scoring "
                        "margin per 48 minutes; the line shows uncertainty across games. "
                        "Crossing zero means the sample does not clearly separate from even.",
                        className="impact-note",
                    ),
                    html.Div(id="trio-status"),
                    html.Div(id="trio-comparison"),
                    control(
                        "SELECT CORE",
                        dcc.Dropdown(
                            id="trio-selection",
                            clearable=False,
                            placeholder="Select a trio to see its full five-player completions",
                        ),
                    ),
                ],
                className="panel",
            ),
            dcc.Loading(html.Div(id="trio-detail"), delay_show=200),
        ],
        id="trio-unit-content",
        style={"display": "none"},
    )


@callback(
    Output("trio-excluded", "options"),
    Output("trio-excluded", "value"),
    Input("lineup-team-selector", "value"),
)
def trio_player_options(team):
    return (get_team_players(team) if team else []), []


@callback(
    Output("trio-selection", "options"),
    Output("trio-selection", "value"),
    Output("trio-comparison", "children"),
    Output("trio-status", "children"),
    Input("lineup-unit-size", "value"),
    Input("lineup-team-selector", "value"),
    Input("lineup-player-selector", "value"),
    Input("trio-excluded", "value"),
    Input("trio-minutes", "value"),
    Input("trio-games", "value"),
    Input("trio-dates", "start_date"),
    Input("trio-dates", "end_date"),
    State("trio-selection", "value"),
)
def matching_trios(unit, team, required, excluded, minutes, games, start, end, current):
    if unit != "3" or not team:
        return (no_update,) * 4
    data = trio_analysis(team, start, end)
    matches = filter_trios(data["summary"], required, excluded, minutes, games)
    options = [
        {
            "label": f"{compact_lineup_names(row.names)} · {row.minutes:,.0f} min / {row.games} G",
            "value": key,
        }
        for key, row in matches.iterrows()
    ]
    selected = current if current in matches.index else matches.index[0] if len(matches) else None
    comparison = core_comparison(matches.head(6), data["games"])
    status = html.Div(
        [
            html.P(
                f"{len(matches)} matching trios. "
                + (
                    f"Comparing {min(6, len(matches))} most-used cores; select any match below."
                    if len(matches)
                    else "Try fewer required players, wider dates, or lower exposure thresholds."
                ),
                className="impact-sample",
            ),
            html.P(
                "Fully validated games only. Full coverage is available with the "
                "selected core’s scoring details.",
                className="impact-note",
            ),
        ]
    )
    return options, selected, comparison, status


@callback(
    Output("trio-detail", "children"),
    Input("lineup-unit-size", "value"),
    Input("lineup-team-selector", "value"),
    Input("trio-selection", "value"),
    Input("trio-dates", "start_date"),
    Input("trio-dates", "end_date"),
)
def show_trio(unit, team, key, start, end):
    if unit != "3":
        return no_update
    if not team or not key:
        return html.Div()
    data = trio_analysis(team, start, end)
    if key not in data["summary"].index:
        return html.Div()
    row = data["summary"].loc[key]
    detail = trio_detail(data, key)
    completion = detail["completions"]
    model = data["model"]
    evidence = f"{row['sample']}. "
    evidence += (
        f"Raw margin / 48: 95% game-bootstrap interval "
        f"{detail['ci'][0]:+.1f} to {detail['ci'][1]:+.1f}."
        if detail["ci"]
        else "A raw-margin interval needs 100 minutes across 10 games."
    )
    most = completion.iloc[0]
    share = row.minutes / data["coverage"]["covered_minutes"] * 100

    def completion_rows(frame):
        return [
            [
                html.Div(
                    [
                        r.partners,
                        html.Br(),
                        dcc.Link(
                            "Plan with this five",
                            href=f"/scenario-planner?team={team}&lineup={r.Index}",
                            className="trio-plan-link",
                        ),
                    ]
                ),
                number(r.minutes),
                int(r.games),
                f"{r.share:.1f}%",
                f"{int(r.points_for)}–{int(r.points_against)}",
                number(r.raw, True),
                "100+ min / 10+ G" if r.minutes >= 100 and r.games >= 10 else "Small sample",
            ]
            for r in frame.itertuples()
        ]

    headers = ["Other two players", "Min", "Games", "Core time", "PF–PA", "Margin / 48", "Exposure"]
    return html.Div(
        [
            html.Div(
                [
                    html.Div("SELECTED CORE", className="section-eyebrow"),
                    html.Div(
                        [
                            player_headshot(int(p), data["names"].get(int(p), p), team)
                            for p in key.split("-")
                        ],
                        className="lineup-headshots trio-headshots",
                    ),
                    html.Div(
                        [
                            metric_card(
                                "MINUTES TOGETHER",
                                f"{row.minutes:,.1f}",
                                f"{share:.1f}% of covered team time",
                            ),
                            metric_card(
                                "GAMES", str(int(row.games)), "Games this trio shared the floor"
                            ),
                            metric_card(
                                "RAW MARGIN / 48",
                                number(row.raw, True),
                                f"{int(row.points_for)} PF · {int(row.points_against)} PA",
                            ),
                            metric_card(
                                "SAMPLE-ADJUSTED / 48",
                                number(row.adjusted, True),
                                "Pulled toward team baseline"
                                if model["available"]
                                else "Calibration unavailable",
                            ),
                        ],
                        className="metric-grid trio-metrics",
                    ),
                    html.P(evidence, className="impact-sample"),
                    html.P(
                        "Exploratory adjustment: the team-only baseline performed better "
                        "in later-game testing. Use raw results and completion context together.",
                        className="impact-note",
                    )
                    if model["available"] and model["adjusted_error"] >= model["baseline_error"]
                    else html.Div(),
                    html.P(
                        f"Most-used completion: {most.partners}, {most.minutes:.1f} minutes "
                        f"({most.share:.1f}% of core time). "
                        "Results vary with the other two players.",
                        className="impact-note",
                    ),
                ],
                className="panel",
            ),
            html.Div(
                [
                    html.H2("Who completed this core?", className="section-title"),
                    html.P(
                        "Each row is a five-player lineup: this trio plus these two players. "
                        "Sorted by minutes. Completion shares sum to 100% across the full list. "
                        "A large trio sample does not validate every completion.",
                        className="impact-note",
                    ),
                    table(headers, completion_rows(completion.head(6))),
                    html.Details(
                        [
                            html.Summary(f"Remaining {max(0, len(completion) - 6)} completions"),
                            table(headers, completion_rows(completion.iloc[6:])),
                        ],
                        className="impact-method",
                    )
                    if len(completion) > 6
                    else html.Div(),
                ],
                className="panel",
            ),
            html.Details(
                [
                    html.Summary("Sample adjustment, validation & scoring coverage"),
                    model_details(model, data["baseline"]),
                    html.P(
                        f"{int(row.boundary_points)} combined points at interval ends. "
                        "Scoring is end-inclusive. Only fully validated games are included. "
                        "Raw uncertainty resamples 2,000 whole games in which this trio appeared; "
                        "it is not a prediction interval for the adjusted estimate. "
                        "No possession ratings, role labels or causal player effects are inferred.",
                        className="impact-note",
                    ),
                    coverage_note(data["coverage"]),
                ],
                className="panel impact-method",
            ),
        ]
    )


def model_details(model, prior):
    if not model["available"]:
        return html.P(
            model["reason"]
            + " Raw results remain available; no default adjusted estimate is invented."
        )
    note = (
        "The adjustment improved on both raw trio rates and the team-only baseline in this holdout."
        if model["adjusted_error"] < min(model["raw_error"], model["baseline_error"])
        else "The adjustment did not beat every simple baseline in this holdout. Treat it as "
        "an exploratory stabilizer, not a validated forecast or recommendation."
    )
    return html.Div(
        [
            html.P(
                f"Adjusted margin = (minutes × raw margin + {model['strength']} × baseline) "
                f"/ (minutes + {model['strength']}). Team baseline: {prior:+.1f} per 48. "
                "The separate trio weight was selected from "
                "0, 24, 48, 100, 200, 400 and 800 minutes."
            ),
            html.P(
                f"Split: {model['train_games']} training games through {model['training_end']}; "
                f"{model['validation_games']} tuning games through {model['validation_end']}; "
                f"{model['test_games']} untouched test games through {model['test_end']}. "
                "The final descriptive estimate uses all filtered games after this audit."
            ),
            table(
                ["Held-out error · points / 48", "Raw trio", "Team only", "Adjusted trio"],
                [
                    [
                        "Lower RMSE is better",
                        number(model["raw_error"]),
                        number(model["baseline_error"]),
                        number(model["adjusted_error"]),
                    ]
                ],
            ),
            html.P(note),
            html.P(
                f"Audit: {model['test_trios']} repeated trios, weighted by later-game exposure. "
                "These overlapping observations are not independent. Roles, teammates, opponents "
                "and schedule can explain differences; no ranking is tuned to player reputation."
            ),
        ]
    )


def core_comparison(top, games):
    """Aligned evidence rows: identity, exposure and results on one shared scale."""
    if top.empty:
        return html.Div()
    estimates = [
        (key, row, raw_confidence(games[games.trio_key == key])) for key, row in top.iterrows()
    ]
    extent = max(abs(value) for _, row, ci in estimates for value in ([row.raw] + (ci or [])))
    limit = max(10, math.ceil(extent / 5) * 5)

    def position(value):
        return 50 + 50 * value / limit

    rows = []
    for _, row, ci in estimates:
        marks = [
            html.Span(className="core-zero"),
            html.Span(className="core-dot", style={"left": f"{position(row.raw)}%"}),
        ]
        if ci:
            marks.insert(
                1,
                html.Span(
                    className="core-range",
                    style={
                        "left": f"{position(ci[0])}%",
                        "width": f"{position(ci[1]) - position(ci[0])}%",
                    },
                ),
            )
        interval = (
            f"95% range {ci[0]:+.1f} to {ci[1]:+.1f}" if ci else "Too little exposure for a range"
        )
        rows.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(name, className="core-name")
                            for name in compact_lineup_names(row.names).split(" · ")
                        ],
                        className="core-identity",
                        title=row.names.replace(" | ", ", "),
                    ),
                    html.Div(
                        [
                            html.Strong(f"{row.minutes:,.0f} min"),
                            html.Span(f"{int(row.games)} games"),
                        ],
                        className="core-exposure",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [html.Strong(f"{row.raw:+.1f}"), html.Span(interval)],
                                className="core-result-label",
                            ),
                            html.Div(
                                marks,
                                className="core-track",
                                role="img",
                                **{"aria-label": f"Margin {row.raw:+.1f} per 48; {interval}"},
                            ),
                        ],
                        className="core-result",
                    ),
                ],
                className="core-evidence-row",
            )
        )
    ranges = [ci for _, _, ci in estimates if ci]
    shared = (
        len(ranges) == len(estimates)
        and len(ranges) > 1
        and max(ci[0] for ci in ranges) <= min(ci[1] for ci in ranges)
    )
    reading = (
        "These cores’ uncertainty ranges all overlap. Their results do not establish "
        "a clear performance ordering; inspect the five-player completions below."
        if shared
        else "Read the result together with its range and exposure. A higher margin alone "
        "does not establish that one core is better than another."
    )
    return html.Div(
        [
            html.P(reading, className="core-reading"),
            html.Div(
                [
                    html.Span("THREE-PLAYER CORE"),
                    html.Span("EXPOSURE"),
                    html.Span("TEAM SCORING MARGIN / 48"),
                ],
                className="core-evidence-header",
            ),
            *rows,
            html.Div(
                [
                    html.Span(f"−{limit} · outscored"),
                    html.Span("0 · even"),
                    html.Span(f"+{limit} · outscored opponent"),
                ],
                className="core-axis",
            ),
            html.P(
                "All rows use the same scale. Ordered by time together, not performance. "
                "Cores overlap and share teammates; these are team results, not isolated player "
                "effects. Choose a core below to see who filled its other two spots.",
                className="impact-note",
            ),
        ],
        className="core-evidence",
    )
