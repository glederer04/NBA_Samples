"""Tests for the tracked production demonstration database."""

import duckdb
import pytest

from rotation_lab.config import DEMO_DATABASE_PATH
from rotation_lab.dashboard import data as dashboard_data
from rotation_lab.demo_database import normalize_team_abbreviations

FEATURED_DEPLOYMENT_TEAMS = {"NYK", "SAS"}


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
        featured_schedules = connection.execute(
            """
            SELECT
                teams.team_abbreviation,
                COUNT(*) AS games
            FROM (
                SELECT home_team_abbreviation AS team_abbreviation
                FROM raw.games

                UNION ALL

                SELECT away_team_abbreviation AS team_abbreviation
                FROM raw.games
            ) AS teams
            WHERE teams.team_abbreviation IN ('NYK', 'SAS')
            GROUP BY teams.team_abbreviation
            """
        ).fetchall()
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

    assert retained_teams == FEATURED_DEPLOYMENT_TEAMS
    assert dict(featured_schedules) == {"NYK": 82, "SAS": 82}
    assert games is not None and games[0] > 0
    assert reviews is not None and reviews[0] > 0
    assert recommendations is not None and recommendations[0] > 0


def test_demo_database_team_aliases_are_normalized() -> None:
    """Charlotte's CLT alias should map to the NBA data's CHA abbreviation."""

    normalized = normalize_team_abbreviations(["clt", "MIA", "mia"])

    assert normalized == ("CHA", "MIA")


def test_demo_database_only_exposes_featured_team_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every dashboard team selector should receive only NYK and SAS."""

    monkeypatch.setattr(
        dashboard_data,
        "DATABASE_PATH",
        DEMO_DATABASE_PATH,
    )

    assert dashboard_data.get_dashboard_teams() == [
        {"label": "NYK", "value": "NYK"},
        {"label": "SAS", "value": "SAS"},
    ]
