"""Build a compact, internally consistent deployment database."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rotation_lab.config import SQL_DIR
from rotation_lab.database import connect_database, initialize_database

TEAM_ABBREVIATION_ALIASES = {
    "CLT": "CHA",
}


@dataclass(frozen=True)
class DemoDatabaseSummary:
    """Counts and size information for one deployment snapshot."""

    excluded_teams: tuple[str, ...]
    retained_teams: int
    retained_games: int
    retained_players: int
    box_score_rows: int
    rotation_rows: int
    play_by_play_rows: int
    source_size_bytes: int
    destination_size_bytes: int


def normalize_team_abbreviations(values: list[str]) -> tuple[str, ...]:
    """Normalize team abbreviations and supported historical aliases."""

    normalized = {
        TEAM_ABBREVIATION_ALIASES.get(value.strip().upper(), value.strip().upper())
        for value in values
        if value.strip()
    }

    if not normalized:
        raise ValueError("At least one excluded team abbreviation is required")

    return tuple(sorted(normalized))


def _attach_source(connection, source_path: Path) -> None:
    escaped_path = str(source_path.resolve()).replace("'", "''")
    connection.execute(f"ATTACH '{escaped_path}' AS source_database (READ_ONLY)")


def _copy_pruned_raw_data(
    source_path: Path,
    destination_path: Path,
    excluded_teams: tuple[str, ...],
) -> None:
    initialize_database(
        database_path=destination_path,
        sql_directory=SQL_DIR,
    )
    connection = connect_database(destination_path)
    placeholders = ", ".join("?" for _ in excluded_teams)

    try:
        connection.execute("BEGIN TRANSACTION")
        _attach_source(connection, source_path)
        connection.execute(
            f"""
            INSERT INTO raw.teams
            SELECT *
            FROM source_database.raw.teams
            WHERE abbreviation NOT IN ({placeholders})
            """,
            list(excluded_teams),
        )
        connection.execute(
            f"""
            INSERT INTO raw.games
            SELECT *
            FROM source_database.raw.games
            WHERE
                home_team_abbreviation NOT IN ({placeholders})
                AND away_team_abbreviation NOT IN ({placeholders})
            """,
            [*excluded_teams, *excluded_teams],
        )
        connection.execute(
            """
            INSERT INTO raw.player_box_scores
            SELECT source_rows.*
            FROM source_database.raw.player_box_scores AS source_rows
            INNER JOIN raw.games AS retained_games
                ON source_rows.game_id = retained_games.game_id
            """
        )
        connection.execute(
            """
            INSERT INTO raw.rotation_stints
            SELECT source_rows.*
            FROM source_database.raw.rotation_stints AS source_rows
            INNER JOIN raw.games AS retained_games
                ON source_rows.game_id = retained_games.game_id
            """
        )
        connection.execute(
            """
            INSERT INTO raw.play_by_play_events
            SELECT source_rows.*
            FROM source_database.raw.play_by_play_events AS source_rows
            INNER JOIN raw.games AS retained_games
                ON source_rows.game_id = retained_games.game_id
            """
        )
        connection.execute(
            """
            INSERT INTO raw.players
            SELECT source_players.*
            FROM source_database.raw.players AS source_players
            WHERE EXISTS (
                SELECT 1
                FROM raw.player_box_scores AS retained_box_scores
                WHERE retained_box_scores.player_id = source_players.player_id
            )
            """
        )
        connection.execute("COMMIT")
        connection.execute("DETACH source_database")
        connection.execute("CHECKPOINT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def _validate_demo_database(
    database_path: Path,
    excluded_teams: tuple[str, ...],
) -> dict[str, int]:
    connection = connect_database(database_path, read_only=True)
    placeholders = ", ".join("?" for _ in excluded_teams)

    try:
        excluded_team_rows = connection.execute(
            f"SELECT COUNT(*) FROM raw.teams WHERE abbreviation IN ({placeholders})",
            list(excluded_teams),
        ).fetchone()[0]
        excluded_game_rows = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM raw.games
            WHERE
                home_team_abbreviation IN ({placeholders})
                OR away_team_abbreviation IN ({placeholders})
            """,
            [*excluded_teams, *excluded_teams],
        ).fetchone()[0]
        orphan_counts = connection.execute(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM raw.player_box_scores AS rows
                    LEFT JOIN raw.games AS games USING (game_id)
                    WHERE games.game_id IS NULL
                )
                + (
                    SELECT COUNT(*)
                    FROM raw.rotation_stints AS rows
                    LEFT JOIN raw.games AS games USING (game_id)
                    WHERE games.game_id IS NULL
                )
                + (
                    SELECT COUNT(*)
                    FROM raw.play_by_play_events AS rows
                    LEFT JOIN raw.games AS games USING (game_id)
                    WHERE games.game_id IS NULL
                )
            """
        ).fetchone()[0]
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM raw.teams) AS retained_teams,
                (SELECT COUNT(*) FROM raw.games) AS retained_games,
                (SELECT COUNT(*) FROM raw.players) AS retained_players,
                (SELECT COUNT(*) FROM raw.player_box_scores) AS box_score_rows,
                (SELECT COUNT(*) FROM raw.rotation_stints) AS rotation_rows,
                (SELECT COUNT(*) FROM raw.play_by_play_events) AS play_by_play_rows,
                (
                    SELECT COUNT(*)
                    FROM marts.box_score_coverage
                    WHERE coverage_status != 'complete'
                ) AS incomplete_box_score_games,
                (
                    SELECT COUNT(*)
                    FROM marts.rotation_coverage
                    WHERE coverage_status != 'complete'
                ) AS incomplete_rotation_games,
                (
                    SELECT COUNT(*)
                    FROM marts.play_by_play_coverage
                    WHERE coverage_status != 'complete'
                ) AS incomplete_play_by_play_games
            """
        ).fetchone()
    finally:
        connection.close()

    if excluded_team_rows or excluded_game_rows or orphan_counts:
        raise ValueError(
            "Deployment database failed referential validation: "
            f"excluded_team_rows={excluded_team_rows}, "
            f"excluded_game_rows={excluded_game_rows}, "
            f"orphan_rows={orphan_counts}"
        )

    count_names = [
        "retained_teams",
        "retained_games",
        "retained_players",
        "box_score_rows",
        "rotation_rows",
        "play_by_play_rows",
        "incomplete_box_score_games",
        "incomplete_rotation_games",
        "incomplete_play_by_play_games",
    ]
    result = dict(zip(count_names, counts, strict=True))
    incomplete_counts = {
        name: count for name, count in result.items() if name.startswith("incomplete_") and count
    }

    if incomplete_counts:
        raise ValueError(f"Deployment database has incomplete retained games: {incomplete_counts}")

    return result


def build_demo_database(
    source_path: Path,
    destination_path: Path,
    excluded_team_abbreviations: list[str],
) -> DemoDatabaseSummary:
    """Build and atomically install a compact deployment snapshot."""

    source_path = source_path.resolve()
    destination_path = destination_path.resolve()

    if source_path == destination_path:
        raise ValueError("Source and destination database paths must be different")

    if not source_path.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source_path}")

    excluded_teams = normalize_team_abbreviations(excluded_team_abbreviations)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.stem}-",
        suffix=".duckdb",
        dir=destination_path.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()

    try:
        _copy_pruned_raw_data(
            source_path=source_path,
            destination_path=temporary_path,
            excluded_teams=excluded_teams,
        )
        counts = _validate_demo_database(
            database_path=temporary_path,
            excluded_teams=excluded_teams,
        )
        temporary_path.replace(destination_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return DemoDatabaseSummary(
        excluded_teams=excluded_teams,
        retained_teams=counts["retained_teams"],
        retained_games=counts["retained_games"],
        retained_players=counts["retained_players"],
        box_score_rows=counts["box_score_rows"],
        rotation_rows=counts["rotation_rows"],
        play_by_play_rows=counts["play_by_play_rows"],
        source_size_bytes=source_path.stat().st_size,
        destination_size_bytes=destination_path.stat().st_size,
    )
