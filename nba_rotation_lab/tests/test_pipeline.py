"""Tests for pipeline run tracking."""

from pathlib import Path

import duckdb
import pytest

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.pipeline import track_pipeline_run


def test_track_pipeline_run_records_completion(tmp_path: Path) -> None:
    """A successful pipeline should record its result."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    with track_pipeline_run(
        pipeline_name="test_pipeline",
        database_path=database_path,
    ) as run:
        run.row_count = 25
        run.message = "Test data loaded"

    connection = duckdb.connect(
        database=str(database_path),
        read_only=True,
    )

    try:
        row = connection.execute(
            """
            SELECT
                pipeline_name,
                status,
                row_count,
                message,
                completed_at IS NOT NULL
            FROM metadata.pipeline_runs
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == (
        "test_pipeline",
        "completed",
        25,
        "Test data loaded",
        True,
    )


def test_track_pipeline_run_records_failure(tmp_path: Path) -> None:
    """A failed pipeline should preserve its error message."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    with pytest.raises(RuntimeError, match="NBA API unavailable"):
        with track_pipeline_run(
            pipeline_name="failing_pipeline",
            database_path=database_path,
        ):
            raise RuntimeError("NBA API unavailable")

    connection = duckdb.connect(
        database=str(database_path),
        read_only=True,
    )

    try:
        row = connection.execute(
            """
            SELECT
                pipeline_name,
                status,
                row_count,
                message,
                completed_at IS NOT NULL
            FROM metadata.pipeline_runs
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == (
        "failing_pipeline",
        "failed",
        None,
        "NBA API unavailable",
        True,
    )
