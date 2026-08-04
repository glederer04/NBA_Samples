"""Tests for the staging and coverage SQL views."""

from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import (
    connect_database,
    initialize_database,
)


def seed_analytics_data(database_path: Path) -> None:
    """Insert two games and one complete game box score."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            INSERT INTO raw.games (
                game_id,
                game_date,
                season_id,
                season_type,
                home_team_id,
                away_team_id,
                home_team_abbreviation,
                away_team_abbreviation,
                home_score,
                away_score,
                game_status
            )
            VALUES
                (
                    '001',
                    '2025-10-21',
                    '22025',
                    'Regular Season',
                    1610612752,
                    1610612738,
                    'NYK',
                    'BOS',
                    112,
                    108,
                    'Final'
                ),
                (
                    '002',
                    '2025-10-22',
                    '22025',
                    'Regular Season',
                    1610612747,
                    1610612744,
                    'LAL',
                    'GSW',
                    105,
                    110,
                    'Final'
                )
            """
        )

        connection.execute(
            """
            INSERT INTO raw.player_box_scores (
                game_id,
                team_id,
                player_id,
                team_abbreviation,
                player_name,
                position,
                minutes,
                starter,
                did_not_play,
                points,
                plus_minus
            )
            VALUES
                (
                    '001',
                    1610612752,
                    1001,
                    'NYK',
                    'Home Player',
                    'G',
                    30.0,
                    TRUE,
                    FALSE,
                    20,
                    4.0
                ),
                (
                    '001',
                    1610612738,
                    1002,
                    'BOS',
                    'Away Player',
                    'F',
                    32.0,
                    TRUE,
                    FALSE,
                    18,
                    -4.0
                )
            """
        )
    finally:
        connection.close()


def test_player_game_staging_adds_game_context(
    tmp_path: Path,
) -> None:
    """The staging view should derive opponent and result fields."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_analytics_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                team_abbreviation,
                game_location,
                opponent_team_abbreviation,
                team_score,
                opponent_score,
                won_game
            FROM staging.player_game_box_scores
            ORDER BY team_abbreviation
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        ("BOS", "away", "NYK", 108, 112, False),
        ("NYK", "home", "BOS", 112, 108, True),
    ]


def test_box_score_coverage_summary(
    tmp_path: Path,
) -> None:
    """Coverage marts should distinguish complete and missing games."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_analytics_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        summary = connection.execute(
            """
            SELECT
                total_games,
                complete_games,
                incomplete_games,
                missing_games,
                coverage_percentage
            FROM marts.box_score_coverage_summary
            """
        ).fetchone()
    finally:
        connection.close()

    assert summary is not None

    assert summary[0] == 2
    assert summary[1] == 1
    assert summary[2] == 0
    assert summary[3] == 1
    assert float(summary[4]) == 50.0
