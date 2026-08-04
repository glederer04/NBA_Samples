"""Print coach-facing five-player lineup performance."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Report five-player lineup performance.")
    parser.add_argument(
        "--team",
        required=True,
        help="Three-letter NBA team abbreviation.",
    )
    parser.add_argument(
        "--minimum-minutes",
        type=float,
        default=2.0,
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
    """Print lineup scoring validation and performance."""

    args = parse_args()
    team_abbreviation = args.team.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        validation = connection.execute(
            """
            SELECT
                COUNT(*) AS covered_games,
                COUNT_IF(score_matches) AS validated_games,
                COALESCE(
                    SUM(
                        CASE
                            WHEN home_team_abbreviation = ?
                                THEN home_boundary_scoring_points
                            ELSE away_boundary_scoring_points
                        END
                    ),
                    0
                ) AS boundary_scoring_points
            FROM marts.lineup_scoring_validation
            WHERE
                home_team_abbreviation = ?
                OR away_team_abbreviation = ?
            """,
            [
                team_abbreviation,
                team_abbreviation,
                team_abbreviation,
            ],
        ).fetchone()

        lineups = connection.execute(
            """
            SELECT
                lineup_names,
                games_used,
                stint_appearances,
                total_minutes,
                points_for,
                points_against,
                plus_minus,
                plus_minus_per_48,
                offensive_points_per_48,
                defensive_points_per_48,
                boundary_scoring_points,
                sample_size_status
            FROM marts.team_lineup_performance
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

    if validation is None or validation[0] == 0:
        print(f"No lineup performance data is available for {team_abbreviation}.")
        return

    covered_games, validated_games, boundary_points = validation

    print(f"{team_abbreviation} lineup performance")
    print("=" * 96)
    print(f"Games with lineup scoring: {covered_games}")
    print(f"Games matching official score: {validated_games}")
    print(f"Boundary scoring points flagged: {boundary_points}")

    if boundary_points:
        print(
            "Boundary note: scoring at an exact substitution "
            "timestamp uses the end-inclusive convention."
        )

    print("\nLineup detail")
    print("-" * 96)

    for lineup_number, lineup in enumerate(
        lineups,
        start=1,
    ):
        (
            lineup_names,
            games_used,
            stint_appearances,
            total_minutes,
            points_for,
            points_against,
            plus_minus,
            plus_minus_per_48,
            offensive_points_per_48,
            defensive_points_per_48,
            lineup_boundary_points,
            sample_size_status,
        ) = lineup

        print(f"{lineup_number}. {lineup_names}")
        print(
            f"   Games: {games_used} | "
            f"Stints: {stint_appearances} | "
            f"Minutes: {float(total_minutes):.2f}"
        )
        print(
            f"   Points: {points_for}-{points_against} | "
            f"Plus-minus: {plus_minus:+d} | "
            f"Plus-minus/48: {float(plus_minus_per_48):+.2f}"
        )
        print(
            f"   Points for/48: "
            f"{float(offensive_points_per_48):.2f} | "
            f"Points against/48: "
            f"{float(defensive_points_per_48):.2f}"
        )
        print(f"   Boundary points: {lineup_boundary_points} | Sample: {sample_size_status}")


if __name__ == "__main__":
    main()
