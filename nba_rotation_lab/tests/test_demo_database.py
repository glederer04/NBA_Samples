"""Tests for the tracked production demonstration database."""

import duckdb

from rotation_lab.config import DEMO_DATABASE_PATH
from rotation_lab.demo_database import normalize_team_abbreviations

EXCLUDED_DEPLOYMENT_TEAMS = {
    "BKN",
    "CHA",
    "CHI",
    "DAL",
    "GSW",
    "IND",
    "LAC",
    "MEM",
    "MIA",
    "MIL",
    "NOP",
    "SAC",
    "UTA",
    "WAS",
}


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
            SELECT abbreviation
            FROM raw.teams
            """
        ).fetchall()
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

    retained_teams = {str(row[0]) for row in teams}

    assert len(retained_teams) == 16
    assert retained_teams.isdisjoint(EXCLUDED_DEPLOYMENT_TEAMS)
    assert games is not None and games[0] > 0
    assert reviews is not None and reviews[0] > 0
    assert recommendations is not None and recommendations[0] > 0


def test_demo_database_team_aliases_are_normalized() -> None:
    """Charlotte's CLT alias should map to the NBA data's CHA abbreviation."""

    normalized = normalize_team_abbreviations(["clt", "MIA", "mia"])

    assert normalized == ("CHA", "MIA")
