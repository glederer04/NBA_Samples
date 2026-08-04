"""Load one NBA game's traditional player box score."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.ingest.box_scores import load_player_box_scores
from rotation_lab.pipeline import track_pipeline_run


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Load one NBA player box score into Rotation Lab.")
    parser.add_argument(
        "--game-id",
        required=True,
        help="Ten-digit NBA game identifier.",
    )

    return parser.parse_args()


def main() -> None:
    """Run player box-score ingestion."""

    args = parse_args()

    with track_pipeline_run(
        pipeline_name="ingest_player_box_score",
        database_path=DATABASE_PATH,
    ) as pipeline_run:
        row_count = load_player_box_scores(game_id=args.game_id)

        pipeline_run.row_count = row_count
        pipeline_run.message = f"Game ID: {args.game_id}"

    print(f"Loaded {row_count} player box-score records")
    print(f"Game ID: {args.game_id}")
    print(f"Pipeline run: {pipeline_run.run_id}")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
