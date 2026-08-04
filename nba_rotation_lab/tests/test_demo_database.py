"""Tests for the tracked production demonstration database."""

import duckdb

from rotation_lab.config import DEMO_DATABASE_PATH


def test_demo_database_contains_dashboard_data() -> None:
    """The deployment snapshot should contain usable public demo data."""

    assert DEMO_DATABASE_PATH.exists()

    connection = duckdb.connect(
        database=str(DEMO_DATABASE_PATH),
        read_only=True,
    )

    try:
        teams = connection.execute(
            """
            SELECT COUNT(*)
            FROM raw.teams
            """
        ).fetchone()
        games = connection.execute(
            """
            SELECT COUNT(*)
            FROM raw.games
            """
        ).fetchone()
        reviews = connection.execute(
            """
            SELECT COUNT(*)
            FROM marts.team_game_review
            """
        ).fetchone()
        recommendations = connection.execute(
            """
            SELECT COUNT(*)
            FROM marts.lineup_recommendation_pool
            """
        ).fetchone()
    finally:
        connection.close()

    assert teams is not None and teams[0] == 30
    assert games is not None and games[0] > 0
    assert reviews is not None and reviews[0] > 0
    assert recommendations is not None and recommendations[0] > 0
