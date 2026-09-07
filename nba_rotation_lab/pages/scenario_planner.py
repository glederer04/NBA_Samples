"""Interactive rotation scenario planning page."""

import logging
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
    format_signed,
    metric_card,
)
from rotation_lab.dashboard.components import get_team_options as get_dashboard_teams
from rotation_lab.dashboard.data import get_planner_recommendations as get_lineup_recommendations
from rotation_lab.modeling import (
    LineupAllocation,
    RotationPlanProjection,
    describe_rotation_plan,
    project_rotation_plan,
)
from rotation_lab.recommendations import (
    LineupRecommendation,
)
from rotation_lab.reporting import generate_scenario_report_bytes

register_page(
    __name__,
    path="/scenario-planner",
    name="Scenario Planner",
    title="Scenario Planner | NBA Rotation Lab",
)


def layout() -> html.Div:
    """Create the interactive Scenario Planner page."""

    team_options = get_dashboard_teams()
    team_values = [option["value"] for option in team_options]

    selected_team = "NYK" if "NYK" in team_values else team_values[0] if team_values else None

    recommendations = (
        get_lineup_recommendations(
            selected_team,
            limit=50,
        )
        if selected_team
        else []
    )

    lineup_options = build_lineup_options(recommendations)
    default_keys, default_minutes = default_plan_values(recommendations)

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "ROTATION PLANNING",
                                className="eyebrow",
                            ),
                            html.H1(
                                "Scenario Planner",
                                className="page-title",
                            ),
                            html.P(
                                "Allocate planned minutes across "
                                "five-player units and compare the "
                                "sample-adjusted plan against the "
                                "current team baseline.",
                                className="page-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label(
                                "TEAM",
                                htmlFor="scenario-team-selector",
                                className="filter-label",
                            ),
                            dcc.Dropdown(
                                id="scenario-team-selector",
                                options=team_options,
                                value=selected_team,
                                clearable=False,
                                maxHeight=360,
                            ),
                        ],
                        className="scenario-team-filter",
                    ),
                ],
                className="page-header scenario-page-header",
            ),
            html.Div(
                [
                    html.Div(
                        "BUILD A PLAN",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Lineup Minute Allocations",
                        className="section-title",
                    ),
                    html.P(
                        "Select up to three unique lineups. Total "
                        "planned minutes cannot exceed 48.",
                        className="scenario-instructions",
                    ),
                    html.Div(
                        [
                            allocation_control(
                                slot="a",
                                title="Lineup A",
                                options=lineup_options,
                                lineup_value=default_keys[0],
                                minutes_value=default_minutes[0],
                            ),
                            allocation_control(
                                slot="b",
                                title="Lineup B",
                                options=lineup_options,
                                lineup_value=default_keys[1],
                                minutes_value=default_minutes[1],
                            ),
                            allocation_control(
                                slot="c",
                                title="Lineup C",
                                options=lineup_options,
                                lineup_value=default_keys[2],
                                minutes_value=default_minutes[2],
                            ),
                        ],
                        className="scenario-allocation-grid",
                    ),
                    html.Div(
                        [
                            html.Label(
                                "REPORT",
                                className="filter-label",
                            ),
                            html.Button(
                                "Download PDF",
                                id="download-scenario-report-button",
                                n_clicks=0,
                                className="report-download-button",
                            ),
                            dcc.Download(
                                id="download-scenario-report",
                            ),
                            html.Div(
                                id="scenario-report-status",
                                className="report-status",
                                role="status",
                            ),
                        ],
                        className=("download-report-control scenario-download-control"),
                    ),
                ],
                className="panel scenario-controls-panel",
            ),
            html.Div(
                id="scenario-metrics",
                className="metric-grid scenario-metric-grid",
            ),
            html.Div(
                [
                    html.Div(
                        "PLAN COMPARISON",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Scenario vs. Team Baseline",
                        className="section-title",
                    ),
                    dcc.Graph(
                        id="scenario-comparison-chart",
                        config={
                            "displayModeBar": False,
                            "responsive": True,
                        },
                    ),
                ],
                className="panel scenario-chart-panel",
            ),
            html.Div(
                id="scenario-readout",
            ),
            html.Div(
                [
                    html.Div(
                        "METHODOLOGY",
                        className="section-eyebrow",
                    ),
                    html.P(
                        "Each lineup uses its sample-adjusted "
                        "plus-minus estimate. Scenario results are "
                        "weighted by planned minutes and compared "
                        "with the team's observed baseline. This "
                        "tool supports staff discussion and should "
                        "not be interpreted as a causal forecast.",
                        className="scenario-methodology-text",
                    ),
                ],
                className="scenario-methodology",
            ),
        ],
        className="page-content",
    )


def allocation_control(
    *,
    slot: str,
    title: str,
    options: list[dict[str, str]],
    lineup_value: str | None,
    minutes_value: float,
) -> html.Div:
    """Create one lineup allocation control."""

    return html.Div(
        [
            html.Div(
                title,
                className="scenario-allocation-title",
            ),
            html.Label(
                "FIVE-PLAYER UNIT",
                htmlFor=f"scenario-lineup-{slot}",
                className="filter-label",
            ),
            dcc.Dropdown(
                id=f"scenario-lineup-{slot}",
                options=options,
                value=lineup_value,
                clearable=True,
                maxHeight=360,
                placeholder="Select a lineup",
            ),
            html.Div(id=f"scenario-lineup-{slot}-summary", className="selected-lineup-summary"),
            html.Label(
                "PLANNED MINUTES",
                htmlFor=f"scenario-minutes-{slot}",
                className="filter-label scenario-minutes-label",
            ),
            dcc.Input(
                id=f"scenario-minutes-{slot}",
                type="number",
                debounce=0.3,
                value=minutes_value,
                min=0,
                max=48,
                step=1,
                className="scenario-minutes-input",
            ),
        ],
        className="scenario-allocation-card",
    )


def build_lineup_options(
    recommendations: list[LineupRecommendation],
) -> list[dict[str, str]]:
    """Convert recommendations into dropdown options."""

    ordered_recommendations = sorted(
        recommendations,
        key=lambda recommendation: (
            -recommendation.total_minutes,
            recommendation.recommendation_rank,
        ),
    )

    return [
        {
            "label": (
                " | ".join(recommendation.player_names)
                + " — "
                + format_signed(recommendation.adjusted_plus_minus_per_48)
                + " adjusted / 48"
            ),
            "value": recommendation.lineup_key,
        }
        for recommendation in ordered_recommendations
    ]


def default_plan_values(
    recommendations: list[LineupRecommendation],
) -> tuple[
    tuple[str | None, str | None, str | None],
    tuple[float, float, float],
]:
    """Create default lineup keys and minute allocations."""

    selected = sorted(
        recommendations,
        key=lambda recommendation: (
            -recommendation.total_minutes,
            recommendation.recommendation_rank,
        ),
    )[:3]

    if len(selected) >= 3:
        keys = (
            selected[0].lineup_key,
            selected[1].lineup_key,
            selected[2].lineup_key,
        )
        minutes = (
            16.0,
            16.0,
            16.0,
        )
    elif len(selected) == 2:
        keys = (
            selected[0].lineup_key,
            selected[1].lineup_key,
            None,
        )
        minutes = (
            24.0,
            24.0,
            0.0,
        )
    elif len(selected) == 1:
        keys = (
            selected[0].lineup_key,
            None,
            None,
        )
        minutes = (
            48.0,
            0.0,
            0.0,
        )
    else:
        keys = (
            None,
            None,
            None,
        )
        minutes = (
            0.0,
            0.0,
            0.0,
        )

    return keys, minutes


def build_scenario_allocations(
    *,
    team_abbreviation: str,
    selections: list[
        tuple[
            str | None,
            int | float | None,
        ]
    ],
) -> list[LineupAllocation]:
    """Build valid lineup allocations from dashboard selections."""

    recommendations = get_lineup_recommendations(
        team_abbreviation,
        limit=50,
    )
    recommendations_by_key = {
        recommendation.lineup_key: recommendation for recommendation in recommendations
    }

    allocations = []

    for lineup_key, planned_minutes in selections:
        if lineup_key is None or planned_minutes is None or float(planned_minutes) <= 0:
            continue

        recommendation = recommendations_by_key.get(lineup_key)

        if recommendation is None:
            continue

        allocations.append(
            LineupAllocation(
                recommendation=recommendation,
                planned_minutes=float(planned_minutes),
            )
        )

    return allocations


@callback(
    Output("scenario-lineup-a", "options"),
    Output("scenario-lineup-a", "value"),
    Output("scenario-lineup-b", "options"),
    Output("scenario-lineup-b", "value"),
    Output("scenario-lineup-c", "options"),
    Output("scenario-lineup-c", "value"),
    Output("scenario-minutes-a", "value"),
    Output("scenario-minutes-b", "value"),
    Output("scenario-minutes-c", "value"),
    Input("scenario-team-selector", "value"),
)
def update_scenario_lineups(
    team_abbreviation: str | None,
) -> tuple:
    """Update lineup options after the team changes."""

    if team_abbreviation is None:
        return (
            [],
            None,
            [],
            None,
            [],
            None,
            0.0,
            0.0,
            0.0,
        )

    recommendations = get_lineup_recommendations(
        team_abbreviation,
        limit=50,
    )
    options = build_lineup_options(recommendations)
    keys, minutes = default_plan_values(recommendations)

    return (
        options,
        keys[0],
        options,
        keys[1],
        options,
        keys[2],
        minutes[0],
        minutes[1],
        minutes[2],
    )


@callback(
    Output("scenario-metrics", "children"),
    Output("scenario-readout", "children"),
    Output("scenario-comparison-chart", "figure"),
    Input("scenario-team-selector", "value"),
    Input("scenario-lineup-a", "value"),
    Input("scenario-lineup-b", "value"),
    Input("scenario-lineup-c", "value"),
    Input("scenario-minutes-a", "value"),
    Input("scenario-minutes-b", "value"),
    Input("scenario-minutes-c", "value"),
)
def calculate_scenario(
    team_abbreviation: str | None,
    lineup_a: str | None,
    lineup_b: str | None,
    lineup_c: str | None,
    minutes_a: int | float | None,
    minutes_b: int | float | None,
    minutes_c: int | float | None,
) -> tuple[list[html.Div], html.Div, go.Figure]:
    """Calculate the selected rotation scenario."""

    if team_abbreviation is None:
        message = "Select a team to begin planning."

        return (
            [],
            scenario_warning(message),
            empty_scenario_figure(message),
        )

    selections = [
        (
            lineup_a,
            minutes_a,
        ),
        (
            lineup_b,
            minutes_b,
        ),
        (
            lineup_c,
            minutes_c,
        ),
    ]

    allocations = build_scenario_allocations(
        team_abbreviation=team_abbreviation,
        selections=selections,
    )

    if not allocations:
        message = "Select at least one lineup with planned minutes."

        return (
            [],
            scenario_warning(message),
            empty_scenario_figure(message),
        )

    try:
        projection = project_rotation_plan(allocations)
    except ValueError as error:
        message = str(error)

        return (
            [],
            scenario_warning(message),
            empty_scenario_figure(message),
        )

    metrics = [
        metric_card(
            label="PLANNED MINUTES",
            value=f"{projection.total_planned_minutes:.1f}",
            detail="Maximum regulation total: 48",
        ),
        metric_card(
            label="SCENARIO +/- 48",
            value=format_signed(projection.weighted_adjusted_plus_minus_per_48),
            detail="Minutes-weighted adjusted estimate",
        ),
        metric_card(
            label="TEAM BASELINE",
            value=format_signed(projection.team_plus_minus_per_48),
            detail="Observed team lineup baseline",
        ),
        metric_card(
            label="PROJECTED DIFFERENCE",
            value=format_signed(projection.projected_margin_difference),
            detail="Across the allocated minutes",
        ),
        metric_card(
            label="CONFIDENCE",
            value=(f"{projection.weighted_confidence_percentage:.1f}%"),
            detail="Minutes-weighted sample confidence",
        ),
    ]

    readout = html.Div(
        [
            html.Div(
                projection.assessment.upper(),
                className=(
                    f"scenario-assessment-badge scenario-assessment-{projection.assessment}"
                ),
            ),
            html.H2(
                "Scenario Readout",
                className="scenario-readout-title",
            ),
            html.P(
                describe_rotation_plan(projection),
                className="scenario-readout-text",
            ),
        ],
        className=(f"scenario-readout scenario-readout-{projection.assessment}"),
    )

    figure = build_scenario_comparison_figure(projection)

    return metrics, readout, figure


@callback(
    Output("download-scenario-report", "data"),
    Output("scenario-report-status", "children"),
    Input("download-scenario-report-button", "n_clicks"),
    State("scenario-team-selector", "value"),
    State("scenario-lineup-a", "value"),
    State("scenario-lineup-b", "value"),
    State("scenario-lineup-c", "value"),
    State("scenario-minutes-a", "value"),
    State("scenario-minutes-b", "value"),
    State("scenario-minutes-c", "value"),
    running=[
        (Output("download-scenario-report-button", "disabled"), True, False),
        (Output("download-scenario-report-button", "children"), "Preparing PDF…", "Download PDF"),
    ],
    prevent_initial_call=True,
)
def handle_scenario_report_download(*args: Any) -> tuple:
    """Keep export failures visible and allow retry without losing the selection."""
    try:
        payload = download_scenario_report(*args)
    except Exception:
        logging.getLogger(__name__).exception("PDF export failed")
        return no_update, "Could not create the PDF. Please retry."
    if payload is no_update:
        return (
            no_update,
            "Use positive minutes totaling at most 48 across unique lineups before downloading.",
        )
    return payload, "PDF ready. Check your browser downloads."


def download_scenario_report(
    n_clicks: int | None,
    team_abbreviation: str | None,
    lineup_a: str | None,
    lineup_b: str | None,
    lineup_c: str | None,
    minutes_a: int | float | None,
    minutes_b: int | float | None,
    minutes_c: int | float | None,
) -> Any:
    """Generate and download the selected rotation scenario."""

    if not n_clicks or team_abbreviation is None:
        return no_update

    selections = [
        (
            lineup_a,
            minutes_a,
        ),
        (
            lineup_b,
            minutes_b,
        ),
        (
            lineup_c,
            minutes_c,
        ),
    ]

    allocations = build_scenario_allocations(
        team_abbreviation=team_abbreviation,
        selections=selections,
    )

    try:
        projection = project_rotation_plan(allocations)
    except ValueError:
        return no_update

    pdf_bytes = generate_scenario_report_bytes(
        allocations=allocations,
        projection=projection,
    )

    normalized_team = team_abbreviation.strip().upper()
    filename = f"{normalized_team}_rotation_scenario_report.pdf"

    return {
        "content": b64encode(pdf_bytes).decode("ascii"),
        "filename": filename,
        "type": "application/pdf",
        "base64": True,
    }


def build_scenario_comparison_figure(
    projection: RotationPlanProjection,
) -> go.Figure:
    """Compare the plan with the team baseline."""

    difference_color = "#16855b" if projection.projected_difference_per_48 >= 0 else "#c5424d"

    labels = [
        "Team Baseline",
        "Scenario Estimate",
        "Difference",
    ]
    values = [
        projection.team_plus_minus_per_48,
        projection.weighted_adjusted_plus_minus_per_48,
        projection.projected_difference_per_48,
    ]

    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=[
                "#8793a5",
                "#2366d1",
                difference_color,
            ],
            text=[format_signed(value) for value in values],
            textposition="outside",
            hovertemplate=("<b>%{x}</b><br>%{y:+.2f} points per 48<extra></extra>"),
        )
    )

    figure.update_layout(
        height=320,
        margin={
            "l": 25,
            "r": 25,
            "t": 25,
            "b": 55,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font={
            "color": "#182235",
        },
        yaxis={
            "title": "Adjusted points per 48",
            "automargin": True,
            "gridcolor": "#e4e9ef",
            "zerolinecolor": "#8793a5",
        },
        xaxis={
            "title": None,
            "automargin": True,
        },
    )

    return figure


def empty_scenario_figure(
    message: str,
) -> go.Figure:
    """Create an empty chart with a planning instruction."""

    figure = go.Figure()

    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={
            "color": "#677489",
            "size": 14,
        },
    )

    figure.update_layout(
        height=320,
        margin={
            "l": 20,
            "r": 20,
            "t": 20,
            "b": 20,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={
            "visible": False,
        },
        yaxis={
            "visible": False,
        },
    )

    return figure


def scenario_warning(message: str) -> html.Div:
    """Create one scenario validation message."""

    return html.Div(
        [
            html.Strong("Plan requires attention"),
            html.P(message),
        ],
        className="scenario-warning",
    )


def selected_lineup_summary(value: str | None, options: list[dict] | None) -> str:
    """Keep the complete selected unit readable even when its dropdown is narrow."""
    return next(
        (option["label"].split(" — ")[0] for option in options or [] if option["value"] == value),
        "No lineup selected.",
    )


for _slot in ("a", "b", "c"):
    callback(
        Output(f"scenario-lineup-{_slot}-summary", "children"),
        Input(f"scenario-lineup-{_slot}", "value"),
        Input(f"scenario-lineup-{_slot}", "options"),
    )(selected_lineup_summary)
