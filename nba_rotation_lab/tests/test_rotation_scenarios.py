"""Tests for rotation-plan scenario projections."""

from datetime import date

import pytest

from rotation_lab.modeling import (
    LineupAllocation,
    describe_rotation_plan,
    project_rotation_plan,
)
from rotation_lab.recommendations import LineupRecommendation


def build_recommendation(
    *,
    lineup_key: str,
    adjusted_plus_minus_per_48: float,
    confidence_percentage: float,
    team_abbreviation: str = "NYK",
) -> LineupRecommendation:
    """Create one scenario-test recommendation."""

    return LineupRecommendation(
        team_abbreviation=team_abbreviation,
        recommendation_rank=1,
        lineup_key=lineup_key,
        player_names=(
            "Player One",
            "Player Two",
            "Player Three",
            "Player Four",
            "Player Five",
        ),
        games_used=10,
        total_minutes=100.0,
        raw_plus_minus_per_48=10.0,
        adjusted_plus_minus_per_48=(adjusted_plus_minus_per_48),
        team_plus_minus_per_48=4.0,
        confidence_percentage=confidence_percentage,
        recommendation="monitor",
        sample_size_status="established",
        latest_game_date=date(2026, 1, 15),
    )


def test_project_rotation_plan_weights_lineup_allocations() -> None:
    """Scenario projections should be weighted by planned minutes."""

    first_lineup = build_recommendation(
        lineup_key="1-2-3-4-5",
        adjusted_plus_minus_per_48=8.0,
        confidence_percentage=60.0,
    )
    second_lineup = build_recommendation(
        lineup_key="6-7-8-9-10",
        adjusted_plus_minus_per_48=2.0,
        confidence_percentage=30.0,
    )

    projection = project_rotation_plan(
        [
            LineupAllocation(
                recommendation=first_lineup,
                planned_minutes=30,
            ),
            LineupAllocation(
                recommendation=second_lineup,
                planned_minutes=18,
            ),
        ]
    )

    assert projection.total_planned_minutes == 48.0
    assert projection.weighted_adjusted_plus_minus_per_48 == 5.75
    assert projection.projected_lineup_margin == 5.75
    assert projection.projected_baseline_margin == 4.0
    assert projection.projected_margin_difference == 1.75
    assert projection.projected_difference_per_48 == 1.75
    assert projection.weighted_confidence_percentage == 48.75
    assert projection.assessment == "neutral"

    description = describe_rotation_plan(projection)

    assert "near the current team baseline" in description
    assert "comparative planning estimate" in description


def test_project_rotation_plan_identifies_positive_plan() -> None:
    """A strong adjusted unit should create a positive scenario."""

    recommendation = build_recommendation(
        lineup_key="1-2-3-4-5",
        adjusted_plus_minus_per_48=8.0,
        confidence_percentage=60.0,
    )

    projection = project_rotation_plan(
        [
            LineupAllocation(
                recommendation=recommendation,
                planned_minutes=24,
            )
        ]
    )

    assert projection.projected_margin_difference == 2.0
    assert projection.projected_difference_per_48 == 4.0
    assert projection.assessment == "positive"


def test_project_rotation_plan_validates_allocations() -> None:
    """Invalid rotation plans should fail clearly."""

    recommendation = build_recommendation(
        lineup_key="1-2-3-4-5",
        adjusted_plus_minus_per_48=8.0,
        confidence_percentage=60.0,
    )

    with pytest.raises(
        ValueError,
        match="allocations cannot be empty",
    ):
        project_rotation_plan([])

    with pytest.raises(
        ValueError,
        match="planned minutes must be greater than zero",
    ):
        project_rotation_plan(
            [
                LineupAllocation(
                    recommendation=recommendation,
                    planned_minutes=0,
                )
            ]
        )

    with pytest.raises(
        ValueError,
        match="cannot exceed 48",
    ):
        project_rotation_plan(
            [
                LineupAllocation(
                    recommendation=recommendation,
                    planned_minutes=49,
                )
            ]
        )

    with pytest.raises(
        ValueError,
        match="each lineup can appear only once",
    ):
        project_rotation_plan(
            [
                LineupAllocation(
                    recommendation=recommendation,
                    planned_minutes=20,
                ),
                LineupAllocation(
                    recommendation=recommendation,
                    planned_minutes=20,
                ),
            ]
        )
