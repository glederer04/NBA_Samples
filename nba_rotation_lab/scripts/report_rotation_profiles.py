"""Print coach-facing player and team rotation profiles."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Report team and player rotation profiles.")
    parser.add_argument(
        "--team",
        required=True,
        help="Three-letter NBA team abbreviation.",
    )
    parser.add_argument(
        "--minimum-games",
        type=int,
        default=1,
        help="Minimum covered games required for a player.",
    )

    return parser.parse_args()


def main() -> None:
    """Print a team rotation summary and player profiles."""

    args = parse_args()
    team_abbreviation = args.team.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        team_profile = connection.execute(
            """
            SELECT
                covered_games,
                players_used,
                average_players_used,
                starter_minutes_percentage,
                bench_scoring_percentage,
                top_five_minutes_percentage,
                rotation_style,
                sample_size_status
            FROM marts.team_rotation_profiles
            WHERE team_abbreviation = ?
            """,
            [team_abbreviation],
        ).fetchone()

        player_profiles = connection.execute(
            """
            SELECT
                player_name,
                games_played,
                games_started,
                average_minutes,
                average_points,
                average_rebounds,
                average_assists,
                points_per_36,
                average_plus_minus,
                rotation_role,
                sample_size_status
            FROM marts.player_rotation_profiles
            WHERE
                team_abbreviation = ?
                AND games_played >= ?
            ORDER BY
                average_minutes DESC,
                player_name
            """,
            [
                team_abbreviation,
                args.minimum_games,
            ],
        ).fetchall()
    finally:
        connection.close()

    if team_profile is None:
        print(f"No rotation-profile data is available for {team_abbreviation}.")
        return

    (
        covered_games,
        players_used,
        average_players_used,
        starter_minutes_percentage,
        bench_scoring_percentage,
        top_five_minutes_percentage,
        rotation_style,
        sample_size_status,
    ) = team_profile

    print(f"{team_abbreviation} rotation profile")
    print("=" * 72)
    print(f"Covered games: {covered_games}")
    print(f"Players used: {players_used}")
    print(f"Average active players: {float(average_players_used):.2f}")
    print(f"Starter minute share: {float(starter_minutes_percentage):.2f}%")
    print(f"Bench scoring share: {float(bench_scoring_percentage):.2f}%")
    print(f"Top-five minute share: {float(top_five_minutes_percentage):.2f}%")
    print(f"Rotation style: {rotation_style}")
    print(f"Sample status: {sample_size_status}")

    print("\nPlayer rotation profiles")
    print("-" * 110)
    print(
        f"{'Player':<24}"
        f"{'GP':>5}"
        f"{'GS':>5}"
        f"{'MIN':>8}"
        f"{'PTS':>8}"
        f"{'REB':>8}"
        f"{'AST':>8}"
        f"{'P/36':>8}"
        f"{'+/-':>8}"
        f"{'Role':>12}"
        f"{'Sample':>14}"
    )
    print("-" * 110)

    for player_profile in player_profiles:
        (
            player_name,
            games_played,
            games_started,
            average_minutes,
            average_points,
            average_rebounds,
            average_assists,
            points_per_36,
            average_plus_minus,
            rotation_role,
            player_sample_status,
        ) = player_profile

        print(
            f"{player_name:<24}"
            f"{games_played:>5}"
            f"{games_started:>5}"
            f"{float(average_minutes):>8.1f}"
            f"{float(average_points):>8.1f}"
            f"{float(average_rebounds):>8.1f}"
            f"{float(average_assists):>8.1f}"
            f"{float(points_per_36):>8.1f}"
            f"{float(average_plus_minus):>8.1f}"
            f"{rotation_role:>12}"
            f"{player_sample_status:>14}"
        )


if __name__ == "__main__":
    main()
