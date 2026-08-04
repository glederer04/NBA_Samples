"""Tests for player and team rotation-profile marts."""

from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import (
    connect_database,
    initialize_database,
)


def seed_rotation_profile_data(database_path: Path) -> None:
    """Insert two games of synthetic rotation data."""

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
                    110,
                    100,
                    'Final'
                ),
                (
                    '002',
                    '2025-10-23',
                    '22025',
                    'Regular Season',
                    1610612752,
                    1610612738,
                    'NYK',
                    'BOS',
                    108,
                    104,
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
                field_goals_made,
                field_goals_attempted,
                three_pointers_made,
                three_pointers_attempted,
                free_throws_made,
                free_throws_attempted,
                total_rebounds,
                assists,
                turnovers,
                points,
                plus_minus
            )
            VALUES
                (
                    '001',
                    1610612752,
                    1001,
                    'NYK',
                    'Core Player',
                    'G',
                    30,
                    TRUE,
                    FALSE,
                    7,
                    15,
                    2,
                    5,
                    4,
                    4,
                    5,
                    4,
                    2,
                    20,
                    6
                ),
                (
                    '002',
                    1610612752,
                    1001,
                    'NYK',
                    'Core Player',
                    'G',
                    36,
                    TRUE,
                    FALSE,
                    10,
                    20,
                    3,
                    7,
                    5,
                    6,
                    7,
                    6,
                    3,
                    28,
                    8
                ),
                (
                    '001',
                    1610612752,
                    1002,
                    'NYK',
                    'Bench Player',
                    '',
                    18,
                    FALSE,
                    FALSE,
                    4,
                    8,
                    1,
                    3,
                    1,
                    2,
                    4,
                    2,
                    1,
                    10,
                    2
                ),
                (
                    '002',
                    1610612752,
                    1002,
                    'NYK',
                    'Bench Player',
                    '',
                    12,
                    FALSE,
                    FALSE,
                    2,
                    5,
                    0,
                    2,
                    2,
                    2,
                    3,
                    1,
                    1,
                    6,
                    -1
                )
            """
        )
    finally:
        connection.close()


def test_player_rotation_profile_calculates_role_metrics(
    tmp_path: Path,
) -> None:
    """Player profiles should summarize role and per-36 production."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_rotation_profile_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        row = connection.execute(
            """
            SELECT
                games_played,
                games_started,
                start_percentage,
                total_minutes,
                average_minutes,
                average_points,
                field_goal_percentage,
                points_per_36,
                rotation_role,
                sample_size_status
            FROM marts.player_rotation_profiles
            WHERE player_id = 1001
            """
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == 2
    assert row[1] == 2
    assert float(row[2]) == 100.0
    assert float(row[3]) == 66.0
    assert float(row[4]) == 33.0
    assert float(row[5]) == 24.0
    assert float(row[6]) == 48.57
    assert float(row[7]) == 26.18
    assert row[8] == "core"
    assert row[9] == "preliminary"


def test_team_rotation_profile_calculates_style(
    tmp_path: Path,
) -> None:
    """Team profiles should summarize depth and minutes allocation."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_rotation_profile_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        row = connection.execute(
            """
            SELECT
                covered_games,
                players_used,
                average_players_used,
                average_team_minutes,
                starter_minutes_percentage,
                bench_scoring_percentage,
                top_five_minutes_percentage,
                rotation_style,
                sample_size_status
            FROM marts.team_rotation_profiles
            WHERE team_abbreviation = 'NYK'
            """
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == 2
    assert row[1] == 2
    assert float(row[2]) == 2.0
    assert float(row[3]) == 48.0
    assert float(row[4]) == 68.75
    assert float(row[5]) == 25.0
    assert float(row[6]) == 100.0
    assert row[7] == "tight"
    assert row[8] == "preliminary"
