"""Coach-facing lineup recommendation dashboard."""

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
    metric_card,
    player_headshot,
)
from rotation_lab.dashboard.data import get_dashboard_teams
from rotation_lab.recommendations import (
    LineupRecommendation,
    describe_lineup_recommendation,
    get_lineup_recommendations,
)

register_page(
    __name__,
    path="/recommendations",
    name="Recommendations",
    title="Recommendations | NBA Rotation Lab",
)


def layout() -> html.Div:
    """Create the lineup recommendation page."""

    team_options = get_dashboard_teams()
    team_values = [option["value"] for option in team_options]

    selected_team = "NYK" if "NYK" in team_values else team_values[0] if team_values else None

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "DECISION SUPPORT",
                                className="eyebrow",
                            ),
                            html.H1(
                                "Lineup Recommendations",
                                className="page-title",
                            ),
                            html.P(
                                "Sample-adjusted five-player unit "
                                "recommendations designed for rotation "
                                "planning and staff discussion.",
                                className="page-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label(
                                "TEAM",
                                className="filter-label",
                            ),
                            dcc.Dropdown(
                                id="recommendation-team-selector",
                                options=team_options,
                                value=selected_team,
                                clearable=False,
                                maxHeight=360,
                            ),
                        ],
                        className="recommendation-team-filter",
                    ),
                ],
                className="page-header recommendation-page-header",
            ),
            html.Div(
                [
                    html.Div(
                        "HOW TO READ THIS PAGE",
                        className="section-eyebrow",
                    ),
                    html.P(
                        "Raw lineup performance is shrunk toward the "
                        "team baseline according to minutes played. "
                        "Small samples receive lower confidence and "
                        "more conservative recommendations.",
                        className="recommendation-methodology",
                    ),
                ],
                className="recommendation-explainer",
            ),
            html.Div(
                id="recommendation-metrics",
                className="metric-grid",
            ),
            html.Div(
                [
                    html.Div(
                        "ROTATION DECISIONS",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Ranked Five-Player Units",
                        className="section-title",
                    ),
                    html.Div(
                        id="recommendation-list",
                        className="recommendation-list",
                    ),
                ],
                className="panel recommendation-panel",
            ),
        ],
        className="page-content",
    )


@callback(
    Output("recommendation-metrics", "children"),
    Output("recommendation-list", "children"),
    Input("recommendation-team-selector", "value"),
)
def update_recommendations(
    team_abbreviation: str | None,
) -> tuple[list[html.Div], list[html.Div]]:
    """Update recommendation metrics and ranked units."""

    if team_abbreviation is None:
        return [], [empty_recommendation_message()]

    recommendations = get_lineup_recommendations(
        team_abbreviation,
        limit=10,
    )

    if not recommendations:
        return [], [empty_recommendation_message()]

    priority_count = sum(
        recommendation.recommendation == "prioritize" for recommendation in recommendations
    )
    exploratory_count = sum(
        recommendation.recommendation == "exploratory" for recommendation in recommendations
    )
    highest_confidence = max(
        recommendation.confidence_percentage for recommendation in recommendations
    )

    metrics = [
        metric_card(
            label="UNITS REVIEWED",
            value=str(len(recommendations)),
            detail="Ranked by adjusted performance",
        ),
        metric_card(
            label="PRIORITY UNITS",
            value=str(priority_count),
            detail="Candidates for additional minutes",
        ),
        metric_card(
            label="EXPLORATORY UNITS",
            value=str(exploratory_count),
            detail="Require a larger sample",
        ),
        metric_card(
            label="TOP CONFIDENCE",
            value=f"{highest_confidence:.1f}%",
            detail="Minutes-based confidence score",
        ),
    ]

    cards = [recommendation_card(recommendation) for recommendation in recommendations]

    return metrics, cards


def recommendation_card(
    recommendation: LineupRecommendation,
) -> html.Div:
    """Create one coach-facing recommendation card."""

    player_ids = [int(player_id) for player_id in recommendation.lineup_key.split("-")]
    players = list(
        zip(
            player_ids,
            recommendation.player_names,
            strict=True,
        )
    )

    tone = recommendation.recommendation

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                f"#{recommendation.recommendation_rank}",
                                className="recommendation-rank",
                            ),
                            html.Span(
                                recommendation.recommendation.upper(),
                                className=(f"recommendation-badge recommendation-{tone}"),
                            ),
                            html.Span(
                                (
                                    f"{recommendation.total_minutes:.1f} MIN"
                                    f" | {recommendation.games_used} G"
                                ),
                                className="recommendation-sample",
                            ),
                        ],
                        className="recommendation-card-heading",
                    ),
                    html.Div(
                        [
                            player_headshot(
                                player_id=player_id,
                                player_name=player_name,
                            )
                            for player_id, player_name in players
                        ],
                        className="lineup-headshots",
                    ),
                ],
                className="recommendation-card-lineup",
            ),
            html.Div(
                [
                    recommendation_stat(
                        label="RAW +/- 48",
                        value=format_signed(recommendation.raw_plus_minus_per_48),
                    ),
                    recommendation_stat(
                        label="ADJUSTED +/- 48",
                        value=format_signed(recommendation.adjusted_plus_minus_per_48),
                    ),
                    recommendation_stat(
                        label="TEAM BASELINE",
                        value=format_signed(recommendation.team_plus_minus_per_48),
                    ),
                    recommendation_stat(
                        label="CONFIDENCE",
                        value=(f"{recommendation.confidence_percentage:.1f}%"),
                    ),
                ],
                className="recommendation-stats",
            ),
            html.P(
                describe_lineup_recommendation(recommendation),
                className="recommendation-explanation",
            ),
            html.Div(
                [
                    html.Span(
                        recommendation.sample_size_status.upper(),
                    ),
                    html.Span(
                        f"Updated {recommendation.latest_game_date}",
                    ),
                ],
                className="recommendation-footer",
            ),
        ],
        className=f"recommendation-card recommendation-card-{tone}",
    )


def recommendation_stat(
    label: str,
    value: str,
) -> html.Div:
    """Create one recommendation metric."""

    return html.Div(
        [
            html.Span(
                label,
                className="recommendation-stat-label",
            ),
            html.Strong(
                value,
                className="recommendation-stat-value",
            ),
        ],
        className="recommendation-stat",
    )


def empty_recommendation_message() -> html.Div:
    """Create the empty recommendation state."""

    return html.Div(
        [
            html.H3("No qualifying lineups"),
            html.P(
                "This team does not currently have a lineup with at least five tracked minutes."
            ),
        ],
        className="empty-state",
    )
