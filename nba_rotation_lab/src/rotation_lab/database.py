"""DuckDB connection and initialization utilities."""

from pathlib import Path

import duckdb

from rotation_lab.config import (
    DATABASE_PATH,
    SQL_DIR,
    ensure_project_directories,
)


def connect_database(
    database_path: Path = DATABASE_PATH,
    *,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection using the project defaults."""

    if not read_only:
        database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(
        database=str(database_path),
        read_only=read_only,
    )
    connection.execute("SET TimeZone = 'UTC'")

    return connection


def read_sql_file(sql_path: Path) -> str:
    """Read one SQL file and reject empty files."""

    sql = sql_path.read_text(encoding="utf-8").strip()

    if not sql:
        raise ValueError(f"SQL file is empty: {sql_path}")

    return sql


def run_sql_file(
    connection: duckdb.DuckDBPyConnection,
    sql_path: Path,
) -> None:
    """Execute one SQL file against an existing connection."""

    connection.execute(read_sql_file(sql_path))


def initialize_database(
    database_path: Path = DATABASE_PATH,
    sql_directory: Path = SQL_DIR,
) -> list[Path]:
    """Create the project schemas and metadata tables."""

    ensure_project_directories()

    sql_files = sorted(sql_directory.glob("**/*.sql"))

    if not sql_files:
        raise FileNotFoundError(f"No SQL files found in {sql_directory}")

    connection = connect_database(database_path)

    try:
        connection.execute("BEGIN TRANSACTION")

        for sql_path in sql_files:
            run_sql_file(connection, sql_path)

        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    return sql_files


def list_user_schemas(
    database_path: Path = DATABASE_PATH,
) -> list[str]:
    """Return the non-system schemas in the project database."""

    connection = connect_database(database_path, read_only=True)

    try:
        rows = connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN (
                'information_schema',
                'main',
                'pg_catalog'
            )
            ORDER BY schema_name
            """
        ).fetchall()
    finally:
        connection.close()

    return [row[0] for row in rows]
