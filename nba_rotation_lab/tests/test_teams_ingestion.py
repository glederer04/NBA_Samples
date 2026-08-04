"""Tests for NBA team reference-data ingestion."""

from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.teams import TEAM_COLUMNS, load_teams


def test_load_teams_inserts_team_records(tmp_path: Path) -> None:
    """Team ingestion should insert normalized records."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    frame = pd.DataFrame(
        [
            {
                "team_id": 1610612752,
                "abbreviation": "NYK",
                "team_name": "New York Knicks",
                "city": "New York",
                "state": "New York",
                "year_founded": 1946,
            }
        ],
        columns=TEAM_COLUMNS,
    )

    row_count = load_teams(database_path=database_path, frame=frame)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        row = connection.execute(
            """
            SELECT
                team_id,
                abbreviation,
                team_name,
                year_founded
            FROM raw.teams
            """
        ).fetchone()
    finally:
        connection.close()

    assert row_count == 1
    assert row == (1610612752, "NYK", "New York Knicks", 1946)


def test_load_teams_is_idempotent(tmp_path: Path) -> None:
    """Loading the same team twice should not create duplicates."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    frame = pd.DataFrame(
        [
            {
                "team_id": 1610612752,
                "abbreviation": "NYK",
                "team_name": "New York Knicks",
                "city": "New York",
                "state": "New York",
                "year_founded": 1946,
            }
        ],
        columns=TEAM_COLUMNS,
    )

    load_teams(database_path=database_path, frame=frame)
    load_teams(database_path=database_path, frame=frame)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM raw.teams
            """
        ).fetchone()
    finally:
        connection.close()

    assert result is not None
    assert result[0] == 1
