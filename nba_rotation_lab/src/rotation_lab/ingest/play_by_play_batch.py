"""Resumable multi-game NBA play-by-play ingestion."""

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database
from rotation_lab.ingest.config import (
    NBA_API_MAX_ATTEMPTS,
    NBA_API_REQUEST_DELAY_SECONDS,
    NBA_API_RETRY_DELAY_SECONDS,
)
from rotation_lab.ingest.play_by_play import load_play_by_play

PlayByPlayLoader = Callable[[str, Path], int]
Sleeper = Callable[[float], None]
ProgressReporter = Callable[[str], None]


@dataclass
class PlayByPlayBatchResult:
    """Summary of a multi-game play-by-play ingestion run."""

    attempted_games: int = 0
    completed_games: int = 0
    loaded_rows: int = 0
    failed_game_ids: list[str] = field(default_factory=list)


def get_pending_play_by_play_game_ids(
    database_path: Path = DATABASE_PATH,
    team_abbreviation: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Return rotation-covered games missing play-by-play data."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    conditions = [
        """
        EXISTS (
            SELECT 1
            FROM raw.rotation_stints AS rotation_stints
            WHERE rotation_stints.game_id = games.game_id
        )
        """,
        """
        NOT EXISTS (
            SELECT 1
            FROM raw.play_by_play_events AS events
            WHERE events.game_id = games.game_id
        )
        """,
    ]
    parameters: list[object] = []

    if team_abbreviation:
        normalized_team = team_abbreviation.strip().upper()

        conditions.append(
            """
            (
                games.home_team_abbreviation = ?
                OR games.away_team_abbreviation = ?
            )
            """
        )
        parameters.extend(
            [
                normalized_team,
                normalized_team,
            ]
        )

    query = f"""
        SELECT games.game_id
        FROM raw.games AS games
        WHERE {" AND ".join(conditions)}
        ORDER BY
            games.game_date,
            games.game_id
    """

    if limit is not None:
        query += "\nLIMIT ?"
        parameters.append(limit)

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()
    finally:
        connection.close()

    return [str(row[0]) for row in rows]


def default_play_by_play_loader(
    game_id: str,
    database_path: Path,
) -> int:
    """Load one game's play-by-play events."""

    return load_play_by_play(
        game_id=game_id,
        database_path=database_path,
    )


def ingest_play_by_play_game_ids(
    game_ids: Iterable[str],
    database_path: Path = DATABASE_PATH,
    max_attempts: int = NBA_API_MAX_ATTEMPTS,
    request_delay_seconds: float = NBA_API_REQUEST_DELAY_SECONDS,
    retry_delay_seconds: float = NBA_API_RETRY_DELAY_SECONDS,
    loader: PlayByPlayLoader = default_play_by_play_loader,
    sleeper: Sleeper = time.sleep,
    report_progress: ProgressReporter = print,
) -> PlayByPlayBatchResult:
    """Load play-by-play games with retry and pacing."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if request_delay_seconds < 0:
        raise ValueError("request_delay_seconds cannot be negative")

    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")

    pending_game_ids = list(game_ids)

    result = PlayByPlayBatchResult(
        attempted_games=len(pending_game_ids),
    )

    for game_number, game_id in enumerate(
        pending_game_ids,
        start=1,
    ):
        report_progress(
            f"[{game_number}/{len(pending_game_ids)}] Loading play-by-play for {game_id}"
        )

        for attempt in range(1, max_attempts + 1):
            try:
                row_count = loader(
                    game_id,
                    database_path,
                )
            except Exception as error:
                if attempt == max_attempts:
                    result.failed_game_ids.append(game_id)

                    report_progress(f"Failed game {game_id} after {max_attempts} attempts: {error}")
                    break

                report_progress(f"Attempt {attempt} failed for {game_id}: {error}. Retrying.")
                sleeper(retry_delay_seconds)
            else:
                result.completed_games += 1
                result.loaded_rows += row_count

                report_progress(f"Completed game {game_id}: {row_count} play-by-play events")
                break

        if game_number < len(pending_game_ids):
            sleeper(request_delay_seconds)

    return result
