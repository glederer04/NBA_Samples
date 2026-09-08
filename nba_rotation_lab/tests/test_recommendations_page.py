"""Tests for the Recommendations dashboard page."""

from datetime import date

import pytest

import app  # noqa: F401  # Import initializes the Dash page registry.
from pages import recommendations as recommendation_page
from rotation_lab.recommendations import LineupRecommendation


def sample_recommendation() -> LineupRecommendation:
    """Create one representative recommendation."""

    return LineupRecommendation(
        team_abbreviation="NYK",
        recommendation_rank=1,
        lineup_key="1-2-3-4-5",
        player_names=(
            "Player One",
            "Player Two",
            "Player Three",
            "Player Four",
            "Player Five",
        ),
        games_used=12,
        total_minutes=120.0,
        raw_plus_minus_per_48=10.0,
        adjusted_plus_minus_per_48=8.0,
        team_plus_minus_per_48=4.0,
        confidence_percentage=60.0,
        recommendation="prioritize",
        sample_size_status="established",
        latest_game_date=date(2026, 1, 15),
    )


def test_recommendation_card_contains_decision_support() -> None:
    """Recommendation cards should expose the important staff context."""

    card = recommendation_page.recommendation_card(sample_recommendation())

    rendered_card = str(card)
    card_properties = card.to_plotly_json()["props"]

    assert card_properties["className"] == ("recommendation-card recommendation-card-prioritize")
    assert "PRIORITIZE" in rendered_card
    assert "ADJUSTED +/- 48" in rendered_card
    assert "SAMPLE WEIGHT" in rendered_card
    assert "Player One" in rendered_card
    assert "decision support" in rendered_card
    assert "Updated 2026-01-15" in rendered_card


def test_update_recommendations_builds_metrics_and_cards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The callback should convert recommendations into page content."""

    recommendation = sample_recommendation()

    def fake_get_lineup_recommendations(
        team_abbreviation: str,
        evidence: str,
    ) -> list[LineupRecommendation]:
        assert team_abbreviation == "NYK"
        assert evidence == "established"
        return [recommendation]

    monkeypatch.setattr(
        recommendation_page,
        "get_evidence_recommendations",
        fake_get_lineup_recommendations,
    )

    metrics, cards = recommendation_page.update_recommendations("NYK")

    assert len(metrics) == 4
    assert len(cards) == 1
    assert "UNITS REVIEWED" in str(metrics[0])
    assert "PRIORITY UNITS" in str(metrics[1])
    assert "1" in str(metrics[1])
    assert "recommendation-card-prioritize" in str(cards[0])


def test_update_recommendations_handles_empty_selection() -> None:
    """An incomplete team selection should produce an empty state."""

    metrics, cards = recommendation_page.update_recommendations(None)

    assert metrics == []
    assert len(cards) == 1
    empty_state_properties = cards[0].to_plotly_json()["props"]

    assert empty_state_properties["className"] == "empty-state"
    assert "No qualifying lineups" in str(cards[0])
