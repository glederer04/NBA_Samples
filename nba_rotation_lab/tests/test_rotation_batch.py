"""Tests for batch rotation ingestion and coverage."""

from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import (
    connect_database,
    initialize_database,
)
from rotation_lab.ingest.rotation_batch import (
    get_pending_rotation_game_ids,
    ingest_rotation_game_ids,
)


def seed_pending_rotation_data(
    database_path: Path,
) -> None:
    """Insert games with different ingestion states."""

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
            VALUES
                (
                    '001',
                    '2025-10-21',
                    1610612752,
                    1610612738,
                    'NYK',
                    'BOS'
                ),
                (
                    '002',
                    '2025-10-22',
                    1610612738,
                    1610612752,
                    'BOS',
                    'NYK'
                ),
                (
                    '003',
                    '2025-10-23',
                    1610612747,
                    1610612744,
                    'LAL',
                    'GSW'
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
                starter,
                did_not_play
            )
            VALUES
                (
                    '001',
                    1610612752,
                    1001,
                    'NYK',
                    'Player One',
                    TRUE,
                    FALSE
                ),
                (
                    '002',
                    1610612738,
                    1002,
                    'BOS',
                    'Player Two',
                    TRUE,
                    FALSE
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
            VALUES (
                '001',
                1610612752,
                1001,
                1,
                'home',
                'Player One',
                1,
                0,
                7200,
                0,
                720,
                720
            )
            """
        )
    finally:
        connection.close()


def test_get_pending_rotation_game_ids(
    tmp_path: Path,
) -> None:
    """Only box-score-covered games without rotations should return."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_pending_rotation_data(database_path)

    all_pending_games = get_pending_rotation_game_ids(
        database_path=database_path,
    )
    knicks_pending_games = get_pending_rotation_game_ids(
        database_path=database_path,
        team_abbreviation="nyk",
    )

    assert all_pending_games == ["002"]
    assert knicks_pending_games == ["002"]


def test_ingest_rotation_game_ids_retries(
    tmp_path: Path,
) -> None:
    """Transient rotation failures should retry successfully."""

    attempts: dict[str, int] = {}
    sleep_calls: list[float] = []
    progress_messages: list[str] = []

    def fake_loader(
        game_id: str,
        database_path: Path,
    ) -> int:
        assert database_path == tmp_path / "test.duckdb"

        attempts[game_id] = attempts.get(game_id, 0) + 1

        if game_id == "001" and attempts[game_id] == 1:
            raise TimeoutError("Temporary rotation timeout")

        return 75

    result = ingest_rotation_game_ids(
        game_ids=["001", "002"],
        database_path=tmp_path / "test.duckdb",
        max_attempts=3,
        request_delay_seconds=0.5,
        retry_delay_seconds=1.0,
        loader=fake_loader,
        sleeper=sleep_calls.append,
        report_progress=progress_messages.append,
    )

    assert result.attempted_games == 2
    assert result.completed_games == 2
    assert result.loaded_rows == 150
    assert result.failed_game_ids == []

    assert attempts == {
        "001": 2,
        "002": 1,
    }
    assert sleep_calls == [1.0, 0.5]
    assert any("Retrying" in message for message in progress_messages)


def test_rotation_coverage_summary(
    tmp_path: Path,
) -> None:
    """A two-team, ten-player rotation should be complete."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

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
                CASE
                    WHEN player_number <= 5
                        THEN 1610612752
                    ELSE 1610612738
                END,
                2000 + player_number,
                1,
                CASE
                    WHEN player_number <= 5
                        THEN 'home'
                    ELSE 'away'
                END,
                'Player ' || CAST(player_number AS VARCHAR),
                1,
                0,
                7200,
                0,
                720,
                720
            FROM range(1, 11) AS players(player_number)
            """
        )

        summary = connection.execute(
            """
            SELECT
                total_games,
                complete_games,
                incomplete_games,
                missing_games,
                coverage_percentage
            FROM marts.rotation_coverage_summary
            """
        ).fetchone()
    finally:
        connection.close()

    assert summary is not None
    assert summary[0] == 1
    assert summary[1] == 1
    assert summary[2] == 0
    assert summary[3] == 0
    assert float(summary[4]) == 100.0
