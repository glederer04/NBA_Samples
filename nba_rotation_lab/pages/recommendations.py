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
from rotation_lab.dashboard.components import get_team_options as get_dashboard_teams
from rotation_lab.dashboard.data import get_evidence_recommendations
from rotation_lab.recommendations import (
    LineupRecommendation,
    describe_lineup_recommendation,
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
                                htmlFor="recommendation-team-selector",
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
                        "The default view requires at least 100 minutes across 10 games. "
                        "Qualifying units are ranked by sample-adjusted margin, not overall "
                        "talent. "
                        "The sample weight is minutes / (minutes + 48); it is not a probability "
                        "that a lineup will succeed. Smaller-sample views are for exploration.",
                        className="recommendation-methodology",
                    ),
                ],
                className="recommendation-explainer",
            ),
            html.Div(
                [
                    html.Label(
                        "EVIDENCE FLOOR",
                        htmlFor="recommendation-evidence",
                        className="filter-label",
                    ),
                    dcc.Dropdown(
                        id="recommendation-evidence",
                        options=[
                            {"label": "Established · 100+ min / 10+ games", "value": "established"},
                            {"label": "Developing · 30+ min / 5+ games", "value": "developing"},
                            {"label": "Exploratory · all units with 5+ min", "value": "all"},
                        ],
                        value="established",
                        clearable=False,
                    ),
                ],
                className="recommendation-evidence-filter",
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
    Input("recommendation-evidence", "value"),
)
def update_recommendations(
    team_abbreviation: str | None,
    evidence: str = "established",
) -> tuple[list[html.Div], list[html.Div]]:
    """Update recommendation metrics and ranked units."""

    if team_abbreviation is None:
        return [], [empty_recommendation_message()]

    recommendations = get_evidence_recommendations(team_abbreviation, evidence)

    if not recommendations:
        return [], [
            html.Div(
                "No units meet this evidence floor. Choose Developing or Exploratory to "
                "inspect smaller samples.",
                className="empty-state",
            )
        ]

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
            label="TOP SAMPLE WEIGHT",
            value=f"{highest_confidence:.1f}%",
            detail="Shrinkage weight, not win probability",
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
                                team_abbreviation=recommendation.team_abbreviation,
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
                        label="SAMPLE WEIGHT",
                        value=(f"{recommendation.confidence_percentage:.1f}%"),
                    ),
                ],
                className="recommendation-stats",
            ),
            html.P(
                describe_lineup_recommendation(recommendation).replace(
                    "confidence score", "sample weight"
                ),
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
