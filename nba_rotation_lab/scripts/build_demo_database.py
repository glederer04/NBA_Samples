"""Build a team-filtered deployment snapshot from the complete local database."""

import argparse
from pathlib import Path

from rotation_lab.config import DATA_DIR
from rotation_lab.demo_database import build_demo_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Build a compact, team-filtered DuckDB deployment snapshot."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=str(DATA_DIR / "db" / "rotation_lab.duckdb"),
        help="Complete local DuckDB source path.",
    )
    parser.add_argument(
        "--destination",
        type=str,
        default=str(DATA_DIR / "demo" / "rotation_lab.duckdb"),
        help="Deployment DuckDB destination path.",
    )
    parser.add_argument(
        "--featured-teams",
        nargs="+",
        required=True,
        help="Selectable teams whose complete schedules should be retained.",
    )

    return parser.parse_args()


def format_megabytes(byte_count: int) -> str:
    """Format bytes as a readable binary-megabyte value."""

    return f"{byte_count / 1024 / 1024:.1f} MB"


def main() -> None:
    """Build and report the deployment snapshot."""

    args = parse_args()
    summary = build_demo_database(
        source_path=Path(args.source).expanduser(),
        destination_path=Path(args.destination).expanduser(),
        featured_team_abbreviations=args.featured_teams,
    )

    print("Deployment database built successfully")
    print(f"Featured teams: {', '.join(summary.featured_teams)}")
    print(f"Retained teams: {summary.retained_teams}")
    print(f"Retained games: {summary.retained_games}")
    print(f"Retained players: {summary.retained_players}")
    print(f"Box-score rows: {summary.box_score_rows:,}")
    print(f"Rotation rows: {summary.rotation_rows:,}")
    print(f"Play-by-play rows: {summary.play_by_play_rows:,}")
    print(f"Source size: {format_megabytes(summary.source_size_bytes)}")
    print(f"Deployment size: {format_megabytes(summary.destination_size_bytes)}")


if __name__ == "__main__":
    main()
