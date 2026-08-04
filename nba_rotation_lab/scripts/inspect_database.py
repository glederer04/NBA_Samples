"""Display a concise summary of the Rotation Lab database."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def main() -> None:
    """Print schemas, tables, row counts, and recent pipeline runs."""

    connection = connect_database(DATABASE_PATH, read_only=True)

    try:
        tables = connection.execute(
            """
            SELECT
                table_schema,
                table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN (
                'information_schema',
                'main',
                'pg_catalog'
            )
            ORDER BY table_schema, table_name
            """
        ).fetchall()

        print(f"Database: {DATABASE_PATH}")
        print("\nTables:")

        for schema_name, table_name in tables:
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'
            ).fetchone()

            count = row_count[0] if row_count is not None else 0

            print(f"  {schema_name}.{table_name}: {count:,} rows")

        pipeline_runs = connection.execute(
            """
            SELECT
                pipeline_name,
                status,
                row_count,
                started_at,
                completed_at,
                message
            FROM metadata.pipeline_runs
            ORDER BY started_at DESC
            LIMIT 10
            """
        ).fetchall()

        print("\nRecent pipeline runs:")

        if not pipeline_runs:
            print("  No pipeline runs recorded")
        else:
            for pipeline_run in pipeline_runs:
                (
                    pipeline_name,
                    status,
                    row_count,
                    started_at,
                    completed_at,
                    message,
                ) = pipeline_run

                print(
                    f"  {pipeline_name}: "
                    f"status={status}, "
                    f"rows={row_count}, "
                    f"started={started_at}, "
                    f"completed={completed_at}, "
                    f"message={message}"
                )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
