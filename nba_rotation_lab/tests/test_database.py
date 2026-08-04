"""Tests for DuckDB initialization."""

from pathlib import Path

import duckdb

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database

EXPECTED_SCHEMAS = {
    "metadata",
    "raw",
    "staging",
    "intermediate",
    "marts",
}


def get_schema_names(database_path: Path) -> set[str]:
    """Return schemas from a test database."""

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        rows = connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            """
        ).fetchall()
    finally:
        connection.close()

    return {row[0] for row in rows}


def test_initialize_database_creates_expected_schemas(tmp_path: Path) -> None:
    """Initialization should create every analytical layer."""

    database_path = tmp_path / "test_rotation_lab.duckdb"

    executed_files = initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    assert database_path.exists()
    assert executed_files
    assert EXPECTED_SCHEMAS.issubset(get_schema_names(database_path))


def test_initialize_database_creates_pipeline_runs_table(
    tmp_path: Path,
) -> None:
    """Initialization should create the pipeline metadata table."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'metadata'
              AND table_name = 'pipeline_runs'
            """
        ).fetchone()
    finally:
        connection.close()

    assert result is not None
    assert result[0] == 1


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    """Running initialization twice should not fail."""

    database_path = tmp_path / "test_rotation_lab.duckdb"

    initialize_database(database_path, SQL_DIR)
    initialize_database(database_path, SQL_DIR)

    assert EXPECTED_SCHEMAS.issubset(get_schema_names(database_path))


def test_initialize_database_creates_raw_reference_tables(
    tmp_path: Path,
) -> None:
    """Initialization should create the initial raw tables."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'raw'
            """
        ).fetchall()
    finally:
        connection.close()

    table_names = {row[0] for row in rows}

    assert {"teams", "players", "games"}.issubset(table_names)
