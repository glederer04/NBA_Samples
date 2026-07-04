from __future__ import annotations

from typing import Dict, Union

import plotly.graph_objects as go

PercentileValue = Union[int, float]
PercentileDict = Dict[str, PercentileValue]


RADAR_LABELS = {
    "SCORING_PCTL": "Scoring",
    "SHOOTING_PCTL": "Shooting",
    "PLAYMAKING_PCTL": "Playmaking",
    "REBOUNDING_PCTL": "Rebounding",
    "DEFENSE_PCTL": "Defense",
    "EFFICIENCY_PCTL": "Efficiency",
    "RIM_PRESSURE_PCTL": "Rim Pressure",
    "CREATION_PCTL": "Creation",
}


def build_radar_chart(
    user_percentiles: PercentileDict,
    title: str = "Player Build Profile",
) -> go.Figure:
    """Build a radar chart from user percentile inputs."""
    categories = list(RADAR_LABELS.values())
    columns = list(RADAR_LABELS.keys())

    values = [float(user_percentiles[column]) for column in columns]

    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            name="Your Build",
            line=dict(color="#1D4ED8", width=3),
            fillcolor="rgba(29, 78, 216, 0.25)",
        )
    )

    fig.update_layout(
        title=title,
        showlegend=False,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[0, 25, 50, 75, 100],
            )
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=450,
    )

    return fig


def build_comparison_radar_chart(
    user_percentiles: PercentileDict,
    comp_percentiles: PercentileDict,
    comp_name: str,
    title: str = "Build vs Top Comp",
) -> go.Figure:
    """Build a radar chart comparing the user profile to a top comp."""
    categories = list(RADAR_LABELS.values())
    columns = list(RADAR_LABELS.keys())

    user_values = [float(user_percentiles[column]) for column in columns]
    comp_values = [float(comp_percentiles[column]) for column in columns]

    categories_closed = categories + [categories[0]]
    user_values_closed = user_values + [user_values[0]]
    comp_values_closed = comp_values + [comp_values[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=user_values_closed,
            theta=categories_closed,
            fill="toself",
            name="Your Build",
            line=dict(color="#1D4ED8", width=3),
            fillcolor="rgba(29, 78, 216, 0.22)",
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=comp_values_closed,
            theta=categories_closed,
            fill="toself",
            name=comp_name,
            line=dict(color="#F97316", width=3),
            fillcolor="rgba(249, 115, 22, 0.18)",
        )
    )

    fig.update_layout(
        title=title,
        showlegend=True,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[0, 25, 50, 75, 100],
            )
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=450,
    )

    return fig
