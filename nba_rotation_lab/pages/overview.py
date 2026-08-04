"""Executive Overview dashboard page."""

from dash import (
    Input,
    Output,
    callback,
    dcc,
    html,
    register_page,
)

from rotation_lab.dashboard.components import (
    format_signed,
    lineup_card,
    metric_card,
)
from rotation_lab.dashboard.data import (
    get_dashboard_teams,
    get_team_overview,
)

register_page(
    __name__,
    path="/",
    name="Executive Overview",
    title="NBA Rotation Lab",
)

TEAM_OPTIONS = get_dashboard_teams()
TEAM_VALUES = [option["value"] for option in TEAM_OPTIONS]
DEFAULT_TEAM = "NYK" if "NYK" in TEAM_VALUES else TEAM_VALUES[0] if TEAM_VALUES else None

layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            "BASKETBALL OPERATIONS",
                            className="eyebrow",
                        ),
                        html.H1(
                            "Executive Overview",
                            className="page-title",
                        ),
                        html.P(
                            "Rotation stability, lineup performance, "
                            "and game-level decision support.",
                            className="page-subtitle",
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Label(
                            "TEAM",
                            htmlFor="team-selector",
                            className="filter-label",
                        ),
                        dcc.Dropdown(
                            id="team-selector",
                            options=TEAM_OPTIONS,
                            value=DEFAULT_TEAM,
                            clearable=False,
                            searchable=False,
                            maxHeight=360,
                            className="team-selector",
                        ),
                    ],
                    className="team-filter",
                ),
            ],
            className="page-header",
        ),
        html.Div(
            id="overview-metrics",
            className="metric-grid",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            "RECENT PERFORMANCE",
                            className="section-eyebrow",
                        ),
                        html.H2(
                            "Game Review",
                            className="section-title",
                        ),
                        html.Div(
                            id="recent-games",
                        ),
                    ],
                    className="panel recent-games-panel",
                ),
                html.Div(
                    [
                        html.Div(
                            "DECISION SUPPORT",
                            className="section-eyebrow",
                        ),
                        html.H2(
                            "Executive Readout",
                            className="section-title",
                        ),
                        html.Div(
                            id="executive-readout",
                        ),
                    ],
                    className="panel insight-panel",
                ),
            ],
            className="overview-grid",
        ),
        html.Div(
            [
                html.Div(
                    "FIVE-PLAYER UNITS",
                    className="section-eyebrow",
                ),
                html.H2(
                    "Most-Used Lineups",
                    className="section-title",
                ),
                html.P(
                    "Lineups are ordered by total minutes. "
                    "Rate statistics should be interpreted alongside "
                    "the displayed sample label.",
                    className="section-description",
                ),
                html.Div(
                    id="top-lineups",
                    className="lineup-list",
                ),
            ],
            className="panel lineup-panel",
        ),
    ],
    className="page-content",
)


@callback(
    Output("overview-metrics", "children"),
    Output("recent-games", "children"),
    Output("executive-readout", "children"),
    Output("top-lineups", "children"),
    Input("team-selector", "value"),
)
def update_overview(
    team_abbreviation: str | None,
) -> tuple:
    """Update the executive overview for one team."""

    if team_abbreviation is None:
        return (
            [],
            html.Div("No team data is available."),
            html.Div("No team data is available."),
            html.Div("No lineup data is available."),
        )

    data = get_team_overview(team_abbreviation)

    metrics = [
        metric_card(
            label="RECORD",
            value=f"{data['wins']}-{data['losses']}",
            detail=(f"{data['covered_games']} covered games"),
        ),
        metric_card(
            label="CUMULATIVE MARGIN",
            value=format_signed(data["cumulative_margin"]),
            detail="Across the current analysis sample",
        ),
        metric_card(
            label="LINEUPS PER GAME",
            value=(f"{data['average_lineups_used']:.1f}"),
            detail="Average unique five-player units",
        ),
        metric_card(
            label="LINEUP CHANGES",
            value=(f"{data['average_lineup_changes']:.1f}"),
            detail="Average interval transitions",
        ),
        metric_card(
            label="DATA VALIDATION",
            value=(f"{data['validated_games']}/{data['covered_games']}"),
            detail="Games matching official scores",
        ),
    ]

    recent_games = build_recent_games(
        data["recent_games"],
        data["team_abbreviation"],
    )
    executive_readout = build_executive_readout(data)

    lineup_cards = [
        lineup_card(
            lineup_key=str(row[0]),
            lineup_names=str(row[1]),
            games_used=int(row[2]),
            total_minutes=float(row[3]),
            points_for=int(row[4]),
            points_against=int(row[5]),
            plus_minus=int(row[6]),
            plus_minus_per_48=float(row[7]),
            sample_size_status=str(row[8]),
        )
        for row in data["top_lineups"]
    ]

    return (
        metrics,
        recent_games,
        executive_readout,
        lineup_cards,
    )


def build_recent_games(
    games: list[tuple],
    team_abbreviation: str,
) -> html.Table:
    """Build the recent-game summary table."""

    rows = []

    for game in games:
        (
            game_id,
            game_date,
            opponent,
            team_location,
            result,
            points_for,
            points_against,
            plus_minus,
            lineups_used,
            best_period,
            worst_period,
        ) = game

        location = "vs" if team_location == "home" else "at"
        result_class = "result-win" if result == "W" else "result-loss"

        rows.append(
            html.Tr(
                [
                    html.Td(str(game_date)),
                    html.Td(f"{location} {opponent}"),
                    html.Td(
                        result,
                        className=result_class,
                    ),
                    html.Td(f"{points_for}-{points_against}"),
                    html.Td(format_signed(plus_minus)),
                    html.Td(str(lineups_used)),
                    html.Td(f"Q{best_period}"),
                    html.Td(f"Q{worst_period}"),
                    html.Td(
                        dcc.Link(
                            str(game_id),
                            href=(f"/game-review/{team_abbreviation}/{game_id}"),
                            className="game-link",
                        )
                    ),
                ]
            )
        )

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Date"),
                        html.Th("Opponent"),
                        html.Th("Result"),
                        html.Th("Score"),
                        html.Th("+/-"),
                        html.Th("Lineups"),
                        html.Th("Best"),
                        html.Th("Worst"),
                        html.Th("Game ID"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="data-table",
    )


def build_executive_readout(
    data: dict,
) -> html.Div:
    """Create deterministic executive insights."""

    games = data["covered_games"]
    margin = data["cumulative_margin"]
    record_margin = data["wins"] - data["losses"]
    validation_complete = data["validated_games"] == games

    if margin > 0:
        margin_text = f"The team is {format_signed(margin)} across the covered sample."
    elif margin < 0:
        margin_text = f"The team is {format_signed(margin)} across the covered sample."
    else:
        margin_text = "The scoring margin is even across the covered sample."

    if record_margin > 0:
        record_text = "The covered sample has a winning record."
    elif record_margin < 0:
        record_text = "The covered sample has a losing record."
    else:
        record_text = "The covered sample is split evenly."

    validation_text = (
        "All analyzed games reconcile to official scores."
        if validation_complete
        else "At least one game requires a data-quality review."
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div("01", className="insight-number"),
                    html.P(record_text),
                ],
                className="insight-row",
            ),
            html.Div(
                [
                    html.Div("02", className="insight-number"),
                    html.P(margin_text),
                ],
                className="insight-row",
            ),
            html.Div(
                [
                    html.Div("03", className="insight-number"),
                    html.P(
                        f"The rotation used an average of "
                        f"{data['average_lineups_used']:.1f} "
                        f"lineups per game."
                    ),
                ],
                className="insight-row",
            ),
            html.Div(
                [
                    html.Div("04", className="insight-number"),
                    html.P(validation_text),
                ],
                className="insight-row",
            ),
        ]
    )
