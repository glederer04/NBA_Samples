"""Tests for atomic five-player lineup intervals."""

from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import (
    connect_database,
    initialize_database,
)


def seed_lineup_interval_data(database_path: Path) -> None:
    """Insert one game containing a home-team substitution."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            INSERT INTO raw.games (
                game_id,
                game_date,
                home_team_id,
                away_team_id,
                home_team_abbreviation,
                away_team_abbreviation
            )
            VALUES (
                '001',
                '2025-10-21',
                1610612752,
                1610612738,
                'NYK',
                'BOS'
            )
            """
        )

        connection.execute(
            """
            INSERT INTO raw.rotation_stints (
                game_id,
                team_id,
                player_id,
                stint_number,
                team_location,
                player_name,
                period,
                in_time_deciseconds,
                out_time_deciseconds,
                in_time_seconds,
                out_time_seconds,
                duration_seconds
            )
            SELECT
                '001',
                1610612752,
                player_number,
                1,
                'home',
                'Home Player '
                    || CAST(player_number AS VARCHAR),
                1,
                0,
                7200,
                0,
                720,
                720
            FROM range(1, 5) AS players(player_number)
            """
        )

        connection.execute(
            """
            INSERT INTO raw.rotation_stints (
                game_id,
                team_id,
                player_id,
                stint_number,
                team_location,
                player_name,
                period,
                in_time_deciseconds,
                out_time_deciseconds,
                in_time_seconds,
                out_time_seconds,
                duration_seconds
            )
            VALUES
                (
                    '001',
                    1610612752,
                    5,
                    1,
                    'home',
                    'Home Player 5',
                    1,
                    0,
                    3600,
                    0,
                    360,
                    360
                ),
                (
                    '001',
                    1610612752,
                    6,
                    1,
                    'home',
                    'Home Player 6',
                    1,
                    3600,
                    7200,
                    360,
                    720,
                    360
                )
            """
        )

        connection.execute(
            """
            INSERT INTO raw.rotation_stints (
                game_id,
                team_id,
                player_id,
                stint_number,
                team_location,
                player_name,
                period,
                in_time_deciseconds,
                out_time_deciseconds,
                in_time_seconds,
                out_time_seconds,
                duration_seconds
            )
            SELECT
                '001',
                1610612738,
                player_number,
                1,
                'away',
                'Away Player '
                    || CAST(player_number AS VARCHAR),
                1,
                0,
                7200,
                0,
                720,
                720
            FROM range(11, 16) AS players(player_number)
            """
        )
    finally:
        connection.close()


def seed_scoring_events(database_path: Path) -> None:
    """Insert scoring events on both sides of a substitution."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            UPDATE raw.games
            SET
                home_score = 4,
                away_score = 3
            WHERE game_id = '001'
            """
        )

        connection.execute(
            """
            INSERT INTO raw.play_by_play_events (
                game_id,
                action_id,
                action_number,
                period,
                clock,
                clock_seconds_remaining,
                game_elapsed_deciseconds,
                team_id,
                team_abbreviation,
                action_type,
                is_field_goal,
                score_home,
                score_away,
                points_total,
                video_available
            )
            VALUES
                (
                    '001',
                    1,
                    1,
                    1,
                    'PT12M00.00S',
                    720,
                    0,
                    NULL,
                    '',
                    'period',
                    FALSE,
                    0,
                    0,
                    0,
                    TRUE
                ),
                (
                    '001',
                    2,
                    2,
                    1,
                    'PT10M20.00S',
                    620,
                    1000,
                    1610612752,
                    'NYK',
                    'Made Shot',
                    TRUE,
                    2,
                    0,
                    2,
                    TRUE
                ),
                (
                    '001',
                    3,
                    3,
                    1,
                    'PT06M10.00S',
                    370,
                    3500,
                    1610612738,
                    'BOS',
                    'Made Shot',
                    TRUE,
                    2,
                    3,
                    5,
                    TRUE
                ),
                (
                    '001',
                    4,
                    4,
                    1,
                    'PT03M40.00S',
                    220,
                    5000,
                    1610612752,
                    'NYK',
                    'Made Shot',
                    TRUE,
                    4,
                    3,
                    7,
                    TRUE
                )
            """
        )
    finally:
        connection.close()


def test_team_lineup_intervals_detect_substitution(
    tmp_path: Path,
) -> None:
    """A substitution should split one lineup into two intervals."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                interval_start_seconds,
                interval_end_seconds,
                duration_seconds,
                lineup_key
            FROM intermediate.team_lineup_intervals
            WHERE team_abbreviation = 'NYK'
            ORDER BY interval_number
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (0.0, 360.0, 360.0, "1-2-3-4-5"),
        (360.0, 720.0, 360.0, "1-2-3-4-6"),
    ]


def test_lineup_interval_coverage_is_complete(
    tmp_path: Path,
) -> None:
    """Two valid five-player teams should give complete coverage."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)

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
                coverage_percentage
            FROM marts.lineup_interval_coverage_summary
            """
        ).fetchone()
    finally:
        connection.close()

    assert summary is not None
    assert summary[0] == 1
    assert summary[1] == 1
    assert summary[2] == 0
    assert float(summary[3]) == 100.0


def test_team_game_lineups_identify_opening_and_closing_units(
    tmp_path: Path,
) -> None:
    """Game-level marts should identify opening and closing units."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                lineup_key,
                stint_appearances,
                total_minutes,
                is_opening_lineup,
                is_closing_lineup
            FROM marts.team_game_lineups
            WHERE team_abbreviation = 'NYK'
            ORDER BY first_entry_deciseconds
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        ("1-2-3-4-5", 1, 6.0, True, False),
        ("1-2-3-4-6", 1, 6.0, False, True),
    ]


def test_team_lineup_usage_and_continuity(
    tmp_path: Path,
) -> None:
    """Usage marts should summarize lineup share and continuity."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        usage_row = connection.execute(
            """
            SELECT
                covered_games,
                games_used,
                total_minutes,
                total_minutes_percentage,
                opening_games,
                closing_games,
                lineup_role,
                sample_size_status
            FROM marts.team_lineup_usage
            WHERE
                team_abbreviation = 'NYK'
                AND lineup_key = '1-2-3-4-5'
            """
        ).fetchone()

        continuity_row = connection.execute(
            """
            SELECT
                covered_games,
                unique_lineups,
                average_lineups_per_game,
                most_used_lineup_percentage,
                continuity_style,
                sample_size_status
            FROM marts.team_lineup_continuity
            WHERE team_abbreviation = 'NYK'
            """
        ).fetchone()
    finally:
        connection.close()

    assert usage_row is not None
    assert usage_row[0] == 1
    assert usage_row[1] == 1
    assert float(usage_row[2]) == 6.0
    assert float(usage_row[3]) == 50.0
    assert usage_row[4] == 1
    assert usage_row[5] == 0
    assert usage_row[6] == "primary"
    assert usage_row[7] == "preliminary"

    assert continuity_row is not None
    assert continuity_row[0] == 1
    assert continuity_row[1] == 2
    assert float(continuity_row[2]) == 2.0
    assert float(continuity_row[3]) == 50.0
    assert continuity_row[4] == "stable"
    assert continuity_row[5] == "preliminary"


def test_scoring_events_derive_score_deltas(
    tmp_path: Path,
) -> None:
    """Consecutive score states should become scoring events."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)
    seed_scoring_events(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                action_id,
                home_points,
                away_points,
                scoring_team_abbreviation
            FROM staging.scoring_events
            ORDER BY action_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (2, 2, 0, "NYK"),
        (3, 0, 3, "BOS"),
        (4, 2, 0, "NYK"),
    ]


def test_lineup_performance_and_score_validation(
    tmp_path: Path,
) -> None:
    """Lineup totals should reproduce the official final score."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)
    seed_scoring_events(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        lineup_rows = connection.execute(
            """
            SELECT
                lineup_key,
                total_minutes,
                points_for,
                points_against,
                plus_minus,
                plus_minus_per_48
            FROM marts.team_lineup_performance
            WHERE team_abbreviation = 'NYK'
            ORDER BY lineup_key
            """
        ).fetchall()

        validation_row = connection.execute(
            """
            SELECT
                official_home_score,
                calculated_home_score,
                official_away_score,
                calculated_away_score,
                score_matches
            FROM marts.lineup_scoring_validation
            WHERE game_id = '001'
            """
        ).fetchone()
    finally:
        connection.close()

    assert lineup_rows == [
        ("1-2-3-4-5", 6.0, 2, 3, -1, -8.0),
        ("1-2-3-4-6", 6.0, 2, 0, 2, 16.0),
    ]

    assert validation_row == (
        4,
        4,
        3,
        3,
        True,
    )


def test_team_game_review_identifies_rotation_outcomes(
    tmp_path: Path,
) -> None:
    """Game-review marts should identify key rotation outcomes."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_lineup_interval_data(database_path)
    seed_scoring_events(database_path)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        review_row = connection.execute(
            """
            SELECT
                points_for,
                points_against,
                plus_minus,
                result,
                rotation_intervals,
                lineups_used,
                lineup_changes,
                best_lineup_key,
                best_lineup_plus_minus,
                worst_lineup_key,
                worst_lineup_plus_minus,
                best_period,
                best_period_plus_minus,
                score_matches
            FROM marts.team_game_review
            WHERE
                game_id = '001'
                AND team_abbreviation = 'NYK'
            """
        ).fetchone()

        period_row = connection.execute(
            """
            SELECT
                period,
                total_minutes,
                points_for,
                points_against,
                plus_minus,
                lineups_used
            FROM marts.team_game_period_performance
            WHERE
                game_id = '001'
                AND team_abbreviation = 'NYK'
            """
        ).fetchone()
    finally:
        connection.close()

    assert review_row == (
        4,
        3,
        1,
        "W",
        2,
        2,
        1,
        "1-2-3-4-6",
        2,
        "1-2-3-4-5",
        -1,
        1,
        1,
        True,
    )

    assert period_row == (
        1,
        12.0,
        4,
        3,
        1,
        2,
    )
