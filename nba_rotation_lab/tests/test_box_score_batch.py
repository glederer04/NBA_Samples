"""Tests for resumable multi-game box-score ingestion."""

from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import (
    connect_database,
    initialize_database,
)
from rotation_lab.ingest.box_score_batch import (
    get_pending_game_ids,
    ingest_game_ids,
)


def seed_games(database_path: Path) -> None:
    """Insert three games and one completed box score."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            INSERT INTO raw.games (
                game_id,
                game_date,
                home_team_abbreviation,
                away_team_abbreviation
            )
            VALUES
                ('001', '2025-10-21', 'NYK', 'BOS'),
                ('002', '2025-10-22', 'BOS', 'NYK'),
                ('003', '2025-10-23', 'LAL', 'GSW')
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
            VALUES (
                '001',
                1610612752,
                1001,
                'NYK',
                'Test Player',
                TRUE,
                FALSE
            )
            """
        )
    finally:
        connection.close()


def test_get_pending_game_ids_supports_resume_and_team_filter(
    tmp_path: Path,
) -> None:
    """Completed games should be skipped and team filters respected."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )
    seed_games(database_path)

    all_pending_games = get_pending_game_ids(
        database_path=database_path,
    )
    knicks_pending_games = get_pending_game_ids(
        database_path=database_path,
        team_abbreviation="nyk",
    )

    assert all_pending_games == ["002", "003"]
    assert knicks_pending_games == ["002"]


def test_ingest_game_ids_retries_and_reports_progress(
    tmp_path: Path,
) -> None:
    """Transient failures should retry without losing progress."""

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
            raise TimeoutError("Temporary NBA API timeout")

        return 20

    result = ingest_game_ids(
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
    assert result.loaded_rows == 40
    assert result.failed_game_ids == []

    assert attempts == {
        "001": 2,
        "002": 1,
    }
    assert sleep_calls == [1.0, 0.5]
    assert any("Retrying" in message for message in progress_messages)
