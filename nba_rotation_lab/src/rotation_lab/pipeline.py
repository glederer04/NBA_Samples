"""Pipeline run tracking utilities."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


@dataclass
class PipelineRun:
    """Mutable information recorded for one pipeline execution."""

    run_id: str
    pipeline_name: str
    row_count: int | None = None
    message: str | None = None


def create_pipeline_run(
    run: PipelineRun,
    database_path: Path = DATABASE_PATH,
) -> None:
    """Insert a running pipeline record."""

    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            INSERT INTO metadata.pipeline_runs (
                run_id,
                pipeline_name,
                status
            )
            VALUES (?, ?, 'running')
            """,
            [
                run.run_id,
                run.pipeline_name,
            ],
        )
    finally:
        connection.close()


def finish_pipeline_run(
    run: PipelineRun,
    status: str,
    database_path: Path = DATABASE_PATH,
    message: str | None = None,
) -> None:
    """Mark a pipeline run as completed or failed."""

    if status not in {"completed", "failed"}:
        raise ValueError(f"Unsupported pipeline status: {status}")

    final_message = message if message is not None else run.message
    connection = connect_database(database_path)

    try:
        connection.execute(
            """
            UPDATE metadata.pipeline_runs
            SET
                completed_at = CURRENT_TIMESTAMP,
                status = ?,
                row_count = ?,
                message = ?
            WHERE run_id = ?
            """,
            [
                status,
                run.row_count,
                final_message,
                run.run_id,
            ],
        )
    finally:
        connection.close()


@contextmanager
def track_pipeline_run(
    pipeline_name: str,
    database_path: Path = DATABASE_PATH,
) -> Iterator[PipelineRun]:
    """Track a pipeline and record either completion or failure."""

    run = PipelineRun(
        run_id=str(uuid4()),
        pipeline_name=pipeline_name,
    )

    create_pipeline_run(
        run=run,
        database_path=database_path,
    )

    try:
        yield run
        if pipeline_name.startswith("ingest_") and any(
            name in pipeline_name for name in ("rotation", "play_by_play", "games")
        ):
            from rotation_lab.lineups.trios import refresh_trios

            refresh_trios(database_path)
    except Exception as error:
        finish_pipeline_run(
            run=run,
            status="failed",
            database_path=database_path,
            message=str(error),
        )
        raise
    else:
        finish_pipeline_run(
            run=run,
            status="completed",
            database_path=database_path,
        )
