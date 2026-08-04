"""Print coach-facing five-player lineup usage."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Report five-player lineup usage.")
    parser.add_argument(
        "--team",
        required=True,
        help="Three-letter NBA team abbreviation.",
    )
    parser.add_argument(
        "--minimum-minutes",
        type=float,
        default=0.0,
        help="Minimum total lineup minutes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Maximum number of lineups to display.",
    )

    return parser.parse_args()


def main() -> None:
    """Print team continuity and lineup usage."""

    args = parse_args()
    team_abbreviation = args.team.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        continuity = connection.execute(
            """
            SELECT
                covered_games,
                unique_lineups,
                average_lineups_per_game,
                opening_lineup_variants,
                closing_lineup_variants,
                most_used_lineup_names,
                most_used_lineup_minutes,
                most_used_lineup_percentage,
                continuity_style,
                sample_size_status
            FROM marts.team_lineup_continuity
            WHERE team_abbreviation = ?
            """,
            [team_abbreviation],
        ).fetchone()

        lineups = connection.execute(
            """
            SELECT
                lineup_names,
                games_used,
                stint_appearances,
                total_minutes,
                total_minutes_percentage,
                opening_games,
                closing_games,
                closing_minutes,
                lineup_role,
                sample_size_status
            FROM marts.team_lineup_usage
            WHERE
                team_abbreviation = ?
                AND total_minutes >= ?
            ORDER BY
                total_minutes DESC,
                lineup_key
            LIMIT ?
            """,
            [
                team_abbreviation,
                args.minimum_minutes,
                args.limit,
            ],
        ).fetchall()
    finally:
        connection.close()

    if continuity is None:
        print(f"No lineup data is available for {team_abbreviation}.")
        return

    (
        covered_games,
        unique_lineups,
        average_lineups_per_game,
        opening_lineup_variants,
        closing_lineup_variants,
        most_used_lineup_names,
        most_used_lineup_minutes,
        most_used_lineup_percentage,
        continuity_style,
        sample_size_status,
    ) = continuity

    print(f"{team_abbreviation} five-player lineup usage")
    print("=" * 90)
    print(f"Covered games: {covered_games}")
    print(f"Unique lineups: {unique_lineups}")
    print(f"Average lineups per game: {float(average_lineups_per_game):.2f}")
    print(f"Opening-lineup variants: {opening_lineup_variants}")
    print(f"Closing-lineup variants: {closing_lineup_variants}")
    print(f"Continuity style: {continuity_style}")
    print(f"Sample status: {sample_size_status}")
    print("\nMost-used lineup:")
    print(f"  {most_used_lineup_names}")
    print(
        f"  {float(most_used_lineup_minutes):.2f} minutes, "
        f"{float(most_used_lineup_percentage):.2f}% "
        f"of team minutes"
    )

    print("\nLineup detail")
    print("-" * 90)

    for lineup_number, lineup in enumerate(
        lineups,
        start=1,
    ):
        (
            lineup_names,
            games_used,
            stint_appearances,
            total_minutes,
            minutes_percentage,
            opening_games,
            closing_games,
            closing_minutes,
            lineup_role,
            lineup_sample_status,
        ) = lineup

        print(f"{lineup_number}. {lineup_names}")
        print(
            f"   Games: {games_used} | "
            f"Stints: {stint_appearances} | "
            f"Minutes: {float(total_minutes):.2f} | "
            f"Share: {float(minutes_percentage):.2f}%"
        )
        print(
            f"   Opened: {opening_games} | "
            f"Closed: {closing_games} | "
            f"Closing minutes: {float(closing_minutes):.2f}"
        )
        print(f"   Role: {lineup_role} | Sample: {lineup_sample_status}")


if __name__ == "__main__":
    main()
