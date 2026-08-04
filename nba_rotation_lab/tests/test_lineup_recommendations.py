"""Tests for coach-facing lineup recommendations."""

from pathlib import Path

import pytest

from rotation_lab.database import connect_database
from rotation_lab.recommendations import (
    describe_lineup_recommendation,
    get_lineup_recommendations,
)


def seed_recommendation_database(
    database_path: Path,
) -> None:
    """Create a small recommendation dataset."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            CREATE SCHEMA marts;

            CREATE TABLE marts.lineup_recommendation_pool (
                team_abbreviation VARCHAR,
                recommendation_rank INTEGER,
                lineup_key VARCHAR,
                lineup_names VARCHAR,
                games_used INTEGER,
                total_minutes DOUBLE,
                plus_minus_per_48 DOUBLE,
                adjusted_plus_minus_per_48 DOUBLE,
                team_plus_minus_per_48 DOUBLE,
                confidence_percentage DOUBLE,
                recommendation VARCHAR,
                sample_size_status VARCHAR,
                latest_game_date DATE
            );

            INSERT INTO marts.lineup_recommendation_pool
            VALUES (
                'NYK',
                1,
                '1-2-3-4-5',
                'Player One | Player Two | Player Three | Player Four | Player Five',
                12,
                120.0,
                10.0,
                8.0,
                4.0,
                60.0,
                'prioritize',
                'established',
                '2026-01-15'
            );
            """
        )
    finally:
        connection.close()


def test_get_lineup_recommendations_returns_ranked_units(
    tmp_path: Path,
) -> None:
    """Recommendation queries should normalize teams and map fields."""

    database_path = tmp_path / "recommendations.duckdb"
    seed_recommendation_database(database_path)

    recommendations = get_lineup_recommendations(
        " nyk ",
        limit=1,
        database_path=database_path,
    )

    assert len(recommendations) == 1

    recommendation = recommendations[0]

    assert recommendation.team_abbreviation == "NYK"
    assert recommendation.recommendation_rank == 1
    assert len(recommendation.player_names) == 5
    assert recommendation.recommendation == "prioritize"
    assert recommendation.baseline_difference == 4.0

    explanation = describe_lineup_recommendation(
        recommendation,
    )

    assert "Prioritize" in explanation
    assert "above the team baseline" in explanation
    assert "decision support" in explanation


def test_get_lineup_recommendations_validates_inputs(
    tmp_path: Path,
) -> None:
    """Invalid query inputs should fail before database access."""

    with pytest.raises(
        ValueError,
        match="team_abbreviation cannot be empty",
    ):
        get_lineup_recommendations(
            " ",
            database_path=tmp_path / "unused.duckdb",
        )

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        get_lineup_recommendations(
            "NYK",
            limit=0,
            database_path=tmp_path / "unused.duckdb",
        )
