"""Rotation-plan scenario projections."""

from dataclasses import dataclass
from typing import Literal

from rotation_lab.recommendations import LineupRecommendation

ScenarioAssessment = Literal[
    "positive",
    "neutral",
    "negative",
]


@dataclass(frozen=True, slots=True)
class LineupAllocation:
    """Planned minutes for one five-player unit."""

    recommendation: LineupRecommendation
    planned_minutes: float


@dataclass(frozen=True, slots=True)
class RotationPlanProjection:
    """Projected result for a collection of lineup allocations."""

    team_abbreviation: str
    total_planned_minutes: float
    weighted_adjusted_plus_minus_per_48: float
    team_plus_minus_per_48: float
    projected_lineup_margin: float
    projected_baseline_margin: float
    projected_margin_difference: float
    projected_difference_per_48: float
    weighted_confidence_percentage: float
    assessment: ScenarioAssessment


def project_rotation_plan(
    allocations: list[LineupAllocation],
) -> RotationPlanProjection:
    """Project a rotation plan from sample-adjusted lineup results."""

    if not allocations:
        raise ValueError("allocations cannot be empty")

    if any(allocation.planned_minutes <= 0 for allocation in allocations):
        raise ValueError("planned minutes must be greater than zero")

    total_planned_minutes = sum(allocation.planned_minutes for allocation in allocations)

    if total_planned_minutes > 48:
        raise ValueError("total planned lineup minutes cannot exceed 48")

    teams = {allocation.recommendation.team_abbreviation for allocation in allocations}

    if len(teams) != 1:
        raise ValueError("all lineup allocations must belong to one team")

    lineup_keys = [allocation.recommendation.lineup_key for allocation in allocations]

    if len(lineup_keys) != len(set(lineup_keys)):
        raise ValueError("each lineup can appear only once in a rotation plan")

    team_abbreviation = allocations[0].recommendation.team_abbreviation
    team_plus_minus_per_48 = allocations[0].recommendation.team_plus_minus_per_48

    weighted_adjusted_plus_minus_per_48 = (
        sum(
            (allocation.recommendation.adjusted_plus_minus_per_48 * allocation.planned_minutes)
            for allocation in allocations
        )
        / total_planned_minutes
    )

    weighted_confidence_percentage = (
        sum(
            (allocation.recommendation.confidence_percentage * allocation.planned_minutes)
            for allocation in allocations
        )
        / total_planned_minutes
    )

    projected_lineup_margin = weighted_adjusted_plus_minus_per_48 * total_planned_minutes / 48
    projected_baseline_margin = team_plus_minus_per_48 * total_planned_minutes / 48
    projected_margin_difference = projected_lineup_margin - projected_baseline_margin
    projected_difference_per_48 = weighted_adjusted_plus_minus_per_48 - team_plus_minus_per_48

    if projected_difference_per_48 >= 3:
        assessment: ScenarioAssessment = "positive"
    elif projected_difference_per_48 <= -3:
        assessment = "negative"
    else:
        assessment = "neutral"

    return RotationPlanProjection(
        team_abbreviation=team_abbreviation,
        total_planned_minutes=round(
            total_planned_minutes,
            2,
        ),
        weighted_adjusted_plus_minus_per_48=round(
            weighted_adjusted_plus_minus_per_48,
            2,
        ),
        team_plus_minus_per_48=round(
            team_plus_minus_per_48,
            2,
        ),
        projected_lineup_margin=round(
            projected_lineup_margin,
            2,
        ),
        projected_baseline_margin=round(
            projected_baseline_margin,
            2,
        ),
        projected_margin_difference=round(
            projected_margin_difference,
            2,
        ),
        projected_difference_per_48=round(
            projected_difference_per_48,
            2,
        ),
        weighted_confidence_percentage=round(
            weighted_confidence_percentage,
            2,
        ),
        assessment=assessment,
    )


def describe_rotation_plan(
    projection: RotationPlanProjection,
) -> str:
    """Create a staff-facing scenario interpretation."""

    if projection.assessment == "positive":
        interpretation = "The proposed allocation grades above the current team baseline."
    elif projection.assessment == "negative":
        interpretation = "The proposed allocation grades below the current team baseline."
    else:
        interpretation = "The proposed allocation grades near the current team baseline."

    return (
        f"{interpretation} The plan projects a "
        f"{projection.projected_margin_difference:+.1f} point "
        f"difference across {projection.total_planned_minutes:.1f} "
        "planned minutes, with a minutes-weighted confidence "
        f"score of {projection.weighted_confidence_percentage:.1f}%. "
        "This is a comparative planning estimate, not a causal "
        "game prediction."
    )
