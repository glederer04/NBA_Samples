"""Inspect five-player lineup intervals and coverage."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Inspect five-player lineup intervals.")
    parser.add_argument(
        "--game-id",
        help="Optional game ID for interval detail.",
    )

    return parser.parse_args()


def format_clock(seconds_remaining: float) -> str:
    """Format period-clock seconds as minutes and seconds."""

    rounded_seconds = int(round(seconds_remaining))
    minutes, seconds = divmod(rounded_seconds, 60)

    return f"{minutes}:{seconds:02d}"


def main() -> None:
    """Print lineup coverage and optional interval detail."""

    args = parse_args()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        summary = connection.execute(
            """
            SELECT
                total_games,
                complete_games,
                incomplete_games,
                coverage_percentage
            FROM marts.lineup_interval_coverage_summary
            """
        ).fetchone()

        interval_rows = []

        if args.game_id:
            interval_rows = connection.execute(
                """
                SELECT
                    team_abbreviation,
                    interval_number,
                    period,
                    period_clock_remaining_seconds,
                    duration_seconds,
                    lineup_names
                FROM intermediate.team_lineup_intervals
                WHERE game_id = ?
                ORDER BY
                    team_abbreviation,
                    interval_start_deciseconds
                """,
                [args.game_id],
            ).fetchall()
    finally:
        connection.close()

    if summary is None:
        print("No lineup intervals are available.")
        return

    (
        total_games,
        complete_games,
        incomplete_games,
        coverage_percentage,
    ) = summary

    print(f"Database: {DATABASE_PATH}")
    print("\nLineup interval coverage:")
    print(f"  Rotation games: {total_games}")
    print(f"  Complete games: {complete_games}")
    print(f"  Incomplete games: {incomplete_games}")
    print(f"  Coverage: {float(coverage_percentage):.2f}%")

    if not args.game_id:
        return

    print(f"\nGame {args.game_id} lineup intervals:")

    for row in interval_rows:
        (
            team_abbreviation,
            interval_number,
            period,
            clock_seconds,
            duration_seconds,
            lineup_names,
        ) = row

        clock = format_clock(float(clock_seconds))

        print(
            f"  {team_abbreviation} "
            f"#{interval_number} "
            f"Q{period} {clock} "
            f"({float(duration_seconds):.1f}s): "
            f"{lineup_names}"
        )


if __name__ == "__main__":
    main()
