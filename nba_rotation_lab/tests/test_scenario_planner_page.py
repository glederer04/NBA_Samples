"""Tests for the Scenario Planner dashboard page."""

from base64 import b64decode
from datetime import date

import pytest
from dash import no_update

import app  # noqa: F401  # Import initializes the Dash page registry.
from pages import scenario_planner
from rotation_lab.modeling import (
    LineupAllocation,
    RotationPlanProjection,
)
from rotation_lab.recommendations import LineupRecommendation


def build_recommendation(
    *,
    lineup_key: str,
    rank: int,
    adjusted_plus_minus_per_48: float,
    confidence_percentage: float,
) -> LineupRecommendation:
    """Create one planner-page recommendation."""

    player_ids = lineup_key.split("-")

    return LineupRecommendation(
        team_abbreviation="NYK",
        recommendation_rank=rank,
        lineup_key=lineup_key,
        player_names=tuple(f"Player {player_id}" for player_id in player_ids),
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


def test_default_plan_values_distributes_minutes() -> None:
    """Three available units should split 48 minutes evenly."""

    recommendations = [
        build_recommendation(
            lineup_key="1-2-3-4-5",
            rank=1,
            adjusted_plus_minus_per_48=8.0,
            confidence_percentage=60.0,
        ),
        build_recommendation(
            lineup_key="6-7-8-9-10",
            rank=2,
            adjusted_plus_minus_per_48=6.0,
            confidence_percentage=50.0,
        ),
        build_recommendation(
            lineup_key="11-12-13-14-15",
            rank=3,
            adjusted_plus_minus_per_48=4.0,
            confidence_percentage=40.0,
        ),
    ]

    keys, minutes = scenario_planner.default_plan_values(recommendations)

    assert keys == (
        "1-2-3-4-5",
        "6-7-8-9-10",
        "11-12-13-14-15",
    )
    assert minutes == (
        16.0,
        16.0,
        16.0,
    )


def test_update_scenario_lineups_builds_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing teams should rebuild lineup options and defaults."""

    recommendations = [
        build_recommendation(
            lineup_key="1-2-3-4-5",
            rank=1,
            adjusted_plus_minus_per_48=8.0,
            confidence_percentage=60.0,
        ),
        build_recommendation(
            lineup_key="6-7-8-9-10",
            rank=2,
            adjusted_plus_minus_per_48=6.0,
            confidence_percentage=50.0,
        ),
    ]

    def fake_get_lineup_recommendations(
        team_abbreviation: str,
        *,
        limit: int,
    ) -> list[LineupRecommendation]:
        assert team_abbreviation == "NYK"
        assert limit == 50
        return recommendations

    monkeypatch.setattr(
        scenario_planner,
        "get_lineup_recommendations",
        fake_get_lineup_recommendations,
    )

    result = scenario_planner.update_scenario_lineups("NYK")

    assert len(result) == 9
    assert len(result[0]) == 2
    assert result[1] == "1-2-3-4-5"
    assert result[3] == "6-7-8-9-10"
    assert result[5] is None
    assert result[6:] == (
        24.0,
        24.0,
        0.0,
    )
    assert "adjusted / 48" in result[0][0]["label"]


def test_calculate_scenario_builds_positive_readout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A positive plan should produce metrics and a readout."""

    recommendations = [
        build_recommendation(
            lineup_key="1-2-3-4-5",
            rank=1,
            adjusted_plus_minus_per_48=8.0,
            confidence_percentage=60.0,
        ),
        build_recommendation(
            lineup_key="6-7-8-9-10",
            rank=2,
            adjusted_plus_minus_per_48=6.0,
            confidence_percentage=50.0,
        ),
    ]

    monkeypatch.setattr(
        scenario_planner,
        "get_lineup_recommendations",
        lambda team_abbreviation, *, limit: recommendations,
    )

    metrics, readout, figure = scenario_planner.calculate_scenario(
        team_abbreviation="NYK",
        lineup_a="1-2-3-4-5",
        lineup_b="6-7-8-9-10",
        lineup_c=None,
        minutes_a=24,
        minutes_b=24,
        minutes_c=0,
    )

    readout_properties = readout.to_plotly_json()["props"]

    assert len(metrics) == 5
    assert "PLANNED MINUTES" in str(metrics[0])
    assert "48.0" in str(metrics[0])
    assert "PROJECTED DIFFERENCE" in str(metrics[3])
    assert readout_properties["className"] == ("scenario-readout scenario-readout-positive")
    assert "Scenario Readout" in str(readout)
    assert "comparative planning estimate" in str(readout)

    figure_data = figure.to_plotly_json()["data"]
    comparison_bar = figure_data[0]

    assert comparison_bar["x"] == [
        "Team Baseline",
        "Scenario Estimate",
        "Difference",
    ]
    assert comparison_bar["y"] == [
        4.0,
        7.0,
        3.0,
    ]


def test_calculate_scenario_handles_duplicate_lineup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate lineup selections should produce a warning."""

    recommendation = build_recommendation(
        lineup_key="1-2-3-4-5",
        rank=1,
        adjusted_plus_minus_per_48=8.0,
        confidence_percentage=60.0,
    )

    monkeypatch.setattr(
        scenario_planner,
        "get_lineup_recommendations",
        lambda team_abbreviation, *, limit: [recommendation],
    )

    metrics, warning, figure = scenario_planner.calculate_scenario(
        team_abbreviation="NYK",
        lineup_a="1-2-3-4-5",
        lineup_b="1-2-3-4-5",
        lineup_c=None,
        minutes_a=24,
        minutes_b=24,
        minutes_c=0,
    )

    warning_properties = warning.to_plotly_json()["props"]

    assert metrics == []
    assert warning_properties["className"] == ("scenario-warning")
    assert "each lineup can appear only once" in str(warning)

    assert figure.to_plotly_json()["data"] == []


def test_download_scenario_report_returns_pdf_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid scenario should produce a downloadable PDF."""

    recommendations = [
        build_recommendation(
            lineup_key="1-2-3-4-5",
            rank=1,
            adjusted_plus_minus_per_48=8.0,
            confidence_percentage=60.0,
        ),
        build_recommendation(
            lineup_key="6-7-8-9-10",
            rank=2,
            adjusted_plus_minus_per_48=6.0,
            confidence_percentage=50.0,
        ),
    ]
    captured_allocations: list[LineupAllocation] = []
    captured_projections: list[RotationPlanProjection] = []

    monkeypatch.setattr(
        scenario_planner,
        "get_lineup_recommendations",
        lambda team_abbreviation, *, limit: recommendations,
    )

    def fake_generate_scenario_report_bytes(
        *,
        allocations: list[LineupAllocation],
        projection: RotationPlanProjection,
    ) -> bytes:
        captured_allocations.extend(allocations)
        captured_projections.append(projection)

        return b"%PDF-test-scenario-report"

    monkeypatch.setattr(
        scenario_planner,
        "generate_scenario_report_bytes",
        fake_generate_scenario_report_bytes,
    )

    result = scenario_planner.download_scenario_report(
        n_clicks=1,
        team_abbreviation="NYK",
        lineup_a="1-2-3-4-5",
        lineup_b="6-7-8-9-10",
        lineup_c=None,
        minutes_a=24,
        minutes_b=24,
        minutes_c=0,
    )

    assert result["filename"] == "NYK_rotation_scenario_report.pdf"
    assert result["type"] == "application/pdf"
    assert result["base64"] is True
    assert b64decode(result["content"]) == b"%PDF-test-scenario-report"

    assert len(captured_allocations) == 2
    assert len(captured_projections) == 1

    projection = captured_projections[0]

    assert projection.total_planned_minutes == 48.0
    assert projection.team_abbreviation == "NYK"


def test_download_scenario_report_requires_valid_inputs() -> None:
    """The download should not run without a completed scenario."""

    result = scenario_planner.download_scenario_report(
        n_clicks=0,
        team_abbreviation="NYK",
        lineup_a=None,
        lineup_b=None,
        lineup_c=None,
        minutes_a=0,
        minutes_b=0,
        minutes_c=0,
    )

    assert result is no_update
