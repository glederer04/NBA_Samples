"""Load an NBA season of completed games into DuckDB."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.ingest.config import DEFAULT_SEASON, DEFAULT_SEASON_TYPE
from rotation_lab.ingest.games import load_games
from rotation_lab.pipeline import track_pipeline_run


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Load NBA games into the Rotation Lab database.")
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--season-type", default=DEFAULT_SEASON_TYPE)

    return parser.parse_args()


def main() -> None:
    """Run game ingestion."""

    args = parse_args()

    with track_pipeline_run(
        pipeline_name="ingest_games",
        database_path=DATABASE_PATH,
    ) as pipeline_run:
        row_count = load_games(
            season=args.season,
            season_type=args.season_type,
        )

        pipeline_run.row_count = row_count
        pipeline_run.message = f"Season: {args.season}; season type: {args.season_type}"

    print(f"Loaded {row_count} NBA games")
    print(f"Season: {args.season}")
    print(f"Season type: {args.season_type}")
    print(f"Pipeline run: {pipeline_run.run_id}")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
