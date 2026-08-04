"""Load missing NBA rotation stints in controlled batches."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.ingest.config import (
    NBA_API_MAX_ATTEMPTS,
    NBA_API_REQUEST_DELAY_SECONDS,
    NBA_API_RETRY_DELAY_SECONDS,
)
from rotation_lab.ingest.rotation_batch import (
    get_pending_rotation_game_ids,
    ingest_rotation_game_ids,
)
from rotation_lab.pipeline import track_pipeline_run


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Load missing NBA player rotation stints.")
    parser.add_argument(
        "--team",
        help="Optional three-letter NBA team abbreviation.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of missing games to load.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=NBA_API_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=NBA_API_REQUEST_DELAY_SECONDS,
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=NBA_API_RETRY_DELAY_SECONDS,
    )

    return parser.parse_args()


def main() -> None:
    """Run resumable rotation-stint ingestion."""

    args = parse_args()

    pending_game_ids = get_pending_rotation_game_ids(
        database_path=DATABASE_PATH,
        team_abbreviation=args.team,
        limit=args.limit,
    )

    if not pending_game_ids:
        print("No missing rotation games matched the request.")
        return

    print(f"Games selected: {len(pending_game_ids)}")

    if args.team:
        print(f"Team filter: {args.team.upper()}")

    with track_pipeline_run(
        pipeline_name="ingest_rotation_stint_batch",
        database_path=DATABASE_PATH,
    ) as pipeline_run:
        result = ingest_rotation_game_ids(
            game_ids=pending_game_ids,
            database_path=DATABASE_PATH,
            max_attempts=args.max_attempts,
            request_delay_seconds=args.request_delay,
            retry_delay_seconds=args.retry_delay,
        )

        pipeline_run.row_count = result.loaded_rows
        pipeline_run.message = (
            f"Attempted games: {result.attempted_games}; "
            f"completed games: {result.completed_games}; "
            f"failed games: {len(result.failed_game_ids)}"
        )

        if result.failed_game_ids:
            failed_games = ", ".join(result.failed_game_ids)

            raise RuntimeError(f"Rotation ingestion failed for: {failed_games}")

    print("Rotation batch ingestion completed")
    print(f"Games attempted: {result.attempted_games}")
    print(f"Games completed: {result.completed_games}")
    print(f"Rotation stints loaded: {result.loaded_rows}")
    print(f"Pipeline run: {pipeline_run.run_id}")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
