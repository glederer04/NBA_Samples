"""Tests for NBA player reference-data ingestion."""

from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.players import PLAYER_COLUMNS, load_players


def test_load_players_inserts_player_records(tmp_path: Path) -> None:
    """Player ingestion should insert normalized records."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    frame = pd.DataFrame(
        [
            {
                "player_id": 2544,
                "full_name": "LeBron James",
                "first_name": "LeBron",
                "last_name": "James",
                "is_active": True,
            }
        ],
        columns=PLAYER_COLUMNS,
    )

    row_count = load_players(database_path=database_path, frame=frame)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        row = connection.execute(
            """
            SELECT
                player_id,
                full_name,
                first_name,
                last_name,
                is_active
            FROM raw.players
            """
        ).fetchone()
    finally:
        connection.close()

    assert row_count == 1
    assert row == (2544, "LeBron James", "LeBron", "James", True)


def test_load_players_is_idempotent(tmp_path: Path) -> None:
    """Loading the same player twice should not create duplicates."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    frame = pd.DataFrame(
        [
            {
                "player_id": 2544,
                "full_name": "LeBron James",
                "first_name": "LeBron",
                "last_name": "James",
                "is_active": True,
            }
        ],
        columns=PLAYER_COLUMNS,
    )

    load_players(database_path=database_path, frame=frame)
    load_players(database_path=database_path, frame=frame)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM raw.players
            """
        ).fetchone()
    finally:
        connection.close()

    assert result is not None
    assert result[0] == 1
