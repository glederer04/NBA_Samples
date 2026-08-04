"""Interactive Game Review dashboard page."""

from base64 import b64encode
from typing import Any

import plotly.graph_objects as go
from dash import (
    Input,
    Output,
    State,
    callback,
    dcc,
    html,
    no_update,
    register_page,
)

from rotation_lab.dashboard.components import (
    format_period_clock,
    format_period_label,
    format_signed,
    lineup_card,
    metric_card,
)
from rotation_lab.dashboard.data import (
    get_dashboard_teams,
    get_game_review,
    get_team_games,
)
from rotation_lab.reporting import generate_game_report_bytes

register_page(
    __name__,
    path="/game-review",
    path_template="/game-review/<team>/<game_id>",
    name="Game Review",
    title="Game Review | NBA Rotation Lab",
)


def layout(
    team: str | None = None,
    game_id: str | None = None,
    **_kwargs: object,
) -> html.Div:
    """Create the Game Review page."""

    team_options = get_dashboard_teams()
    team_values = [option["value"] for option in team_options]

    selected_team = (
        team.strip().upper()
        if team and team.strip().upper() in team_values
        else "NYK"
        if "NYK" in team_values
        else team_values[0]
        if team_values
        else None
    )

    game_options = get_team_games(selected_team) if selected_team else []
    game_values = [option["value"] for option in game_options]

    selected_game = game_id if game_id in game_values else game_values[0] if game_values else None

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "GAME ANALYSIS",
                                className="eyebrow",
                            ),
                            html.H1(
                                "Game Review",
                                className="page-title",
                            ),
                            html.P(
                                "Period performance, lineup outcomes, "
                                "and high-leverage rotation stretches.",
                                className="page-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label(
                                        "TEAM",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="review-team-selector",
                                        options=team_options,
                                        value=selected_team,
                                        clearable=False,
                                        maxHeight=360,
                                    ),
                                ],
                                className="review-filter",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "GAME",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="review-game-selector",
                                        options=game_options,
                                        value=selected_game,
                                        clearable=False,
                                        maxHeight=360,
                                    ),
                                ],
                                className="review-filter game-filter",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "REPORT",
                                        className="filter-label",
                                    ),
                                    html.Button(
                                        "Download PDF",
                                        id="download-game-report-button",
                                        n_clicks=0,
                                        className="report-download-button",
                                    ),
                                ],
                                className="download-report-control",
                            ),
                            dcc.Download(
                                id="download-game-report",
                            ),
                        ],
                        className="review-filter-row",
                    ),
                ],
                className="page-header review-page-header",
            ),
            html.Div(
                id="game-review-metrics",
                className="metric-grid",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "PERIOD PERFORMANCE",
                                className="section-eyebrow",
                            ),
                            html.H2(
                                "Scoring Margin by Period",
                                className="section-title",
                            ),
                            dcc.Graph(
                                id="period-margin-chart",
                                className="period-margin-graph",
                                config={
                                    "displayModeBar": False,
                                    "responsive": True,
                                },
                            ),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.Div(
                                "COACHING READOUT",
                                className="section-eyebrow",
                            ),
                            html.H2(
                                "Game Takeaways",
                                className="section-title",
                            ),
                            html.Div(
                                id="game-takeaways",
                            ),
                        ],
                        className="panel insight-panel",
                    ),
                ],
                className="game-review-grid",
            ),
            html.Div(
                [
                    html.Div(
                        "ROTATION WINDOWS",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Best and Worst Stretches",
                        className="section-title",
                    ),
                    html.Div(
                        id="rotation-stretches",
                        className="stretch-grid",
                    ),
                ],
                className="panel",
            ),
            html.Div(
                [
                    html.Div(
                        "FIVE-PLAYER UNITS",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Most-Used Game Lineups",
                        className="section-title",
                    ),
                    html.Div(
                        id="game-lineups",
                        className="lineup-list",
                    ),
                ],
                className="panel game-lineup-panel",
            ),
        ],
        className="page-content",
    )


@callback(
    Output("review-game-selector", "options"),
    Output("review-game-selector", "value"),
    Input("review-team-selector", "value"),
    State("review-game-selector", "value"),
)
def update_game_options(
    team_abbreviation: str | None,
    current_game_id: str | None,
) -> tuple[list[dict[str, str]], str | None]:
    """Update game choices after a team selection."""

    if team_abbreviation is None:
        return [], None

    options = get_team_games(team_abbreviation)
    values = [option["value"] for option in options]

    selected_game = current_game_id if current_game_id in values else values[0] if values else None

    return options, selected_game


@callback(
    Output("download-game-report", "data"),
    Input("download-game-report-button", "n_clicks"),
    State("review-team-selector", "value"),
    State("review-game-selector", "value"),
    prevent_initial_call=True,
)
def download_game_report(
    n_clicks: int | None,
    team_abbreviation: str | None,
    game_id: str | None,
) -> Any:
    """Generate and download the selected game report."""

    if not n_clicks or team_abbreviation is None or game_id is None:
        return no_update

    data = get_game_review(
        team_abbreviation=team_abbreviation,
        game_id=game_id,
    )

    if data is None:
        return no_update

    normalized_team = team_abbreviation.strip().upper()
    normalized_game_id = game_id.strip()

    filename = f"{normalized_team}_{normalized_game_id}_game_report.pdf"

    pdf_bytes = generate_game_report_bytes(
        data=data,
    )

    return {
        "content": b64encode(pdf_bytes).decode("ascii"),
        "filename": filename,
        "type": "application/pdf",
        "base64": True,
    }


@callback(
    Output("game-review-metrics", "children"),
    Output("period-margin-chart", "figure"),
    Output("game-takeaways", "children"),
    Output("rotation-stretches", "children"),
    Output("game-lineups", "children"),
    Input("review-team-selector", "value"),
    Input("review-game-selector", "value"),
)
def update_game_review(
    team_abbreviation: str | None,
    game_id: str | None,
) -> tuple:
    """Update the complete Game Review page."""

    if team_abbreviation is None or game_id is None:
        return empty_game_review()

    data = get_game_review(
        team_abbreviation=team_abbreviation,
        game_id=game_id,
    )

    if data is None:
        return empty_game_review()

    matchup_location = "vs." if data["team_location"] == "home" else "at"

    metrics = [
        metric_card(
            label="MATCHUP",
            value=(f"{matchup_location} {data['opponent']}"),
            detail=str(data["game_date"]),
        ),
        metric_card(
            label="RESULT",
            value=(f"{data['result']} {data['points_for']}-{data['points_against']}"),
            detail=(f"Margin {format_signed(data['plus_minus'])}"),
        ),
        metric_card(
            label="LINEUPS USED",
            value=str(data["lineups_used"]),
            detail=(f"{data['rotation_intervals']} intervals"),
        ),
        metric_card(
            label="LINEUP CHANGES",
            value=str(data["lineup_changes"]),
            detail="Rotation interval transitions",
        ),
        metric_card(
            label="SCORE VALIDATION",
            value=("PASSED" if data["score_matches"] else "REVIEW"),
            detail=(f"{data['boundary_scoring_points']} boundary points flagged"),
        ),
    ]

    figure = build_period_figure(data["periods"])
    takeaways = build_takeaways(data)
    stretches = build_stretch_sections(data["stretches"])

    lineups = [
        lineup_card(
            lineup_key=str(row[0]),
            lineup_names=str(row[1]),
            games_used=1,
            total_minutes=float(row[2]),
            points_for=int(row[3]),
            points_against=int(row[4]),
            plus_minus=int(row[5]),
            plus_minus_per_48=float(row[6]),
            sample_size_status="single game",
        )
        for row in data["lineups"]
    ]

    return (
        metrics,
        figure,
        takeaways,
        stretches,
        lineups,
    )


def build_period_figure(
    periods: list[tuple],
) -> go.Figure:
    """Create a period scoring-margin chart."""

    labels = [format_period_label(int(row[0])) for row in periods]
    margins = [int(row[3]) for row in periods]
    colors = ["#16855b" if margin >= 0 else "#c5424d" for margin in margins]

    figure = go.Figure(
        go.Bar(
            x=labels,
            y=margins,
            marker_color=colors,
            text=[format_signed(margin) for margin in margins],
            textposition="outside",
            customdata=[
                [
                    int(row[1]),
                    int(row[2]),
                    int(row[4]),
                ]
                for row in periods
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Margin: %{y:+d}<br>"
                "Score: %{customdata[0]}-"
                "%{customdata[1]}<br>"
                "Lineups: %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        margin={
            "l": 20,
            "r": 20,
            "t": 25,
            "b": 55,
        },
        height=260,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        yaxis={
            "title": "Point margin",
            "automargin": True,
            "gridcolor": "#e4e9ef",
            "zerolinecolor": "#8793a5",
        },
        xaxis={
            "title": None,
            "automargin": True,
        },
        font={
            "color": "#182235",
        },
    )

    return figure


def build_takeaways(
    data: dict[str, Any],
) -> html.Div:
    """Create deterministic game-level takeaways."""

    return html.Div(
        [
            insight_row(
                "01",
                (
                    f"{format_period_label(data['best_period'])} "
                    f"was the strongest period at "
                    f"{format_signed(data['best_period_plus_minus'])}."
                ),
            ),
            insight_row(
                "02",
                (
                    f"{format_period_label(data['worst_period'])} "
                    f"was the weakest period at "
                    f"{format_signed(data['worst_period_plus_minus'])}."
                ),
            ),
            insight_row(
                "03",
                (
                    f"The staff used {data['lineups_used']} "
                    f"unique lineups and "
                    f"{data['lineup_changes']} lineup changes."
                ),
            ),
            insight_row(
                "04",
                (
                    f"{data['boundary_scoring_points']} scoring "
                    f"points occurred at exact rotation boundaries."
                ),
            ),
        ]
    )


def insight_row(
    number: str,
    text: str,
) -> html.Div:
    """Create one numbered insight."""

    return html.Div(
        [
            html.Div(
                number,
                className="insight-number",
            ),
            html.P(text),
        ],
        className="insight-row",
    )


def build_stretch_sections(
    stretches: list[tuple],
) -> list[html.Div]:
    """Create best and worst rotation-stretch lists."""

    best_stretches = sorted(
        stretches,
        key=lambda row: (
            int(row[7]),
            float(row[3]),
        ),
        reverse=True,
    )[:3]
    worst_stretches = sorted(
        stretches,
        key=lambda row: (
            int(row[7]),
            -float(row[3]),
        ),
    )[:3]

    return [
        stretch_column(
            title="Best Stretches",
            stretches=best_stretches,
            tone="positive",
        ),
        stretch_column(
            title="Worst Stretches",
            stretches=worst_stretches,
            tone="negative",
        ),
    ]


def stretch_column(
    title: str,
    stretches: list[tuple],
    tone: str,
) -> html.Div:
    """Create one ranked stretch column."""

    return html.Div(
        [
            html.H3(
                title,
                className="stretch-column-title",
            ),
            *[
                stretch_card(
                    rank=rank,
                    stretch=stretch,
                    tone=tone,
                )
                for rank, stretch in enumerate(
                    stretches,
                    start=1,
                )
            ],
        ],
        className="stretch-column",
    )


def stretch_card(
    rank: int,
    stretch: tuple,
    tone: str,
) -> html.Div:
    """Create one rotation-stretch card."""

    (
        period,
        start_deciseconds,
        end_deciseconds,
        duration_seconds,
        lineup_names,
        points_for,
        points_against,
        plus_minus,
        boundary_points,
    ) = stretch

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        f"#{rank}",
                        className="stretch-rank",
                    ),
                    html.Strong(
                        format_signed(int(plus_minus)),
                        className=f"stretch-margin {tone}",
                    ),
                ],
                className="stretch-card-header",
            ),
            html.Div(
                (
                    f"{format_period_clock(period, start_deciseconds)} "
                    f"to "
                    f"{format_period_clock(period, end_deciseconds)}"
                ),
                className="stretch-time",
            ),
            html.Div(
                (f"{float(duration_seconds):.1f} seconds | {points_for}-{points_against}"),
                className="stretch-score",
            ),
            html.Div(
                lineup_names,
                className="stretch-lineup",
            ),
            html.Div(
                f"Boundary points: {boundary_points}",
                className="stretch-boundary",
            ),
        ],
        className="stretch-card",
    )


def empty_game_review() -> tuple:
    """Return empty dashboard outputs."""

    empty_figure = go.Figure()
    empty_message = html.Div(
        "No game-review data is available.",
        className="empty-state",
    )

    return (
        [],
        empty_figure,
        empty_message,
        [],
        [],
    )
