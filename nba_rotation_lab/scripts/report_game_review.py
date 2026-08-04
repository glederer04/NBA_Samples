"""Print a coach-facing review of one team's game rotations."""

import argparse

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Report one team's game-level rotation performance."
    )
    parser.add_argument(
        "--team",
        required=True,
        help="Three-letter NBA team abbreviation.",
    )
    parser.add_argument(
        "--game-id",
        help="Optional ten-digit NBA game identifier.",
    )
    parser.add_argument(
        "--minimum-stretch-seconds",
        type=float,
        default=60.0,
        help="Minimum stretch duration for best/worst stretch rankings.",
    )

    return parser.parse_args()


def format_period(period: int) -> str:
    """Return a basketball-friendly period label."""

    if period <= 4:
        return f"Q{period}"

    return f"OT{period - 4}"


def format_game_clock(
    period: int,
    elapsed_deciseconds: int,
) -> str:
    """Convert game-elapsed time into a period clock."""

    if period <= 4:
        period_start = (period - 1) * 7200
        period_length = 7200
    else:
        period_start = 28800 + (period - 5) * 3000
        period_length = 3000

    elapsed_in_period = elapsed_deciseconds - period_start
    remaining_deciseconds = max(
        period_length - elapsed_in_period,
        0,
    )
    remaining_seconds = round(remaining_deciseconds / 10)
    minutes, seconds = divmod(remaining_seconds, 60)

    return f"{format_period(period)} {minutes}:{seconds:02d}"


def main() -> None:
    """Print one team-game rotation review."""

    args = parse_args()
    team_abbreviation = args.team.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        game_id = args.game_id

        if game_id is None:
            game_row = connection.execute(
                """
                SELECT game_id
                FROM marts.team_game_review
                WHERE team_abbreviation = ?
                ORDER BY
                    game_date DESC,
                    game_id DESC
                LIMIT 1
                """,
                [team_abbreviation],
            ).fetchone()

            if game_row is None:
                print(f"No game-review data is available for {team_abbreviation}.")
                return

            game_id = str(game_row[0])

        review = connection.execute(
            """
            SELECT
                game_date,
                opponent_team_abbreviation,
                team_location,
                points_for,
                points_against,
                plus_minus,
                result,
                rotation_intervals,
                lineups_used,
                lineup_changes,
                boundary_scoring_points,
                best_lineup_names,
                best_lineup_minutes,
                best_lineup_plus_minus,
                worst_lineup_names,
                worst_lineup_minutes,
                worst_lineup_plus_minus,
                best_period,
                best_period_points_for,
                best_period_points_against,
                best_period_plus_minus,
                worst_period,
                worst_period_points_for,
                worst_period_points_against,
                worst_period_plus_minus,
                score_matches
            FROM marts.team_game_review
            WHERE
                game_id = ?
                AND team_abbreviation = ?
            """,
            [
                game_id,
                team_abbreviation,
            ],
        ).fetchone()

        periods = connection.execute(
            """
            SELECT
                period,
                points_for,
                points_against,
                plus_minus,
                lineups_used,
                rotation_intervals
            FROM marts.team_game_period_performance
            WHERE
                game_id = ?
                AND team_abbreviation = ?
            ORDER BY period
            """,
            [
                game_id,
                team_abbreviation,
            ],
        ).fetchall()

        best_stretches = connection.execute(
            """
            SELECT
                period,
                interval_start_deciseconds,
                interval_end_deciseconds,
                duration_seconds,
                lineup_names,
                points_for,
                points_against,
                plus_minus
            FROM marts.team_game_rotation_stretches
            WHERE
                game_id = ?
                AND team_abbreviation = ?
                AND duration_seconds >= ?
            ORDER BY
                plus_minus DESC,
                duration_seconds DESC,
                interval_number
            LIMIT 3
            """,
            [
                game_id,
                team_abbreviation,
                args.minimum_stretch_seconds,
            ],
        ).fetchall()

        worst_stretches = connection.execute(
            """
            SELECT
                period,
                interval_start_deciseconds,
                interval_end_deciseconds,
                duration_seconds,
                lineup_names,
                points_for,
                points_against,
                plus_minus
            FROM marts.team_game_rotation_stretches
            WHERE
                game_id = ?
                AND team_abbreviation = ?
                AND duration_seconds >= ?
            ORDER BY
                plus_minus,
                duration_seconds DESC,
                interval_number
            LIMIT 3
            """,
            [
                game_id,
                team_abbreviation,
                args.minimum_stretch_seconds,
            ],
        ).fetchall()
    finally:
        connection.close()

    if review is None:
        print(f"No review is available for {team_abbreviation} in game {game_id}.")
        return

    (
        game_date,
        opponent,
        team_location,
        points_for,
        points_against,
        plus_minus,
        result,
        rotation_intervals,
        lineups_used,
        lineup_changes,
        boundary_points,
        best_lineup_names,
        best_lineup_minutes,
        best_lineup_plus_minus,
        worst_lineup_names,
        worst_lineup_minutes,
        worst_lineup_plus_minus,
        best_period,
        best_period_points_for,
        best_period_points_against,
        best_period_plus_minus,
        worst_period,
        worst_period_points_for,
        worst_period_points_against,
        worst_period_plus_minus,
        score_matches,
    ) = review

    location_text = "vs." if team_location == "home" else "at"

    print(f"{team_abbreviation} game rotation review")
    print("=" * 100)
    print(f"Game: {game_id}")
    print(f"Date: {game_date}")
    print(f"Matchup: {team_abbreviation} {location_text} {opponent}")
    print(f"Result: {result}, {points_for}-{points_against} ({plus_minus:+d})")
    print(f"Official-score validation: {score_matches}")
    print(
        f"Rotation: {lineups_used} lineups, "
        f"{rotation_intervals} intervals, "
        f"{lineup_changes} lineup changes"
    )
    print(f"Boundary scoring points flagged: {boundary_points}")

    print("\nPeriod performance")
    print("-" * 100)

    for period_row in periods:
        (
            period,
            period_points_for,
            period_points_against,
            period_plus_minus,
            period_lineups,
            period_intervals,
        ) = period_row

        print(
            f"{format_period(period)}: "
            f"{period_points_for}-{period_points_against} "
            f"({period_plus_minus:+d}) | "
            f"{period_lineups} lineups | "
            f"{period_intervals} intervals"
        )

    print("\nLineup summary")
    print("-" * 100)
    print(
        f"Best: {best_lineup_names}\n"
        f"  {float(best_lineup_minutes):.2f} minutes, "
        f"{best_lineup_plus_minus:+d}"
    )
    print(
        f"Worst: {worst_lineup_names}\n"
        f"  {float(worst_lineup_minutes):.2f} minutes, "
        f"{worst_lineup_plus_minus:+d}"
    )

    print("\nBest rotation stretches")
    print("-" * 100)
    print_stretches(best_stretches)

    print("\nWorst rotation stretches")
    print("-" * 100)
    print_stretches(worst_stretches)

    print("\nCoach-facing takeaways")
    print("-" * 100)
    print(
        f"1. {format_period(best_period)} was the strongest period: "
        f"{best_period_points_for}-{best_period_points_against} "
        f"({best_period_plus_minus:+d})."
    )
    print(
        f"2. {format_period(worst_period)} was the weakest period: "
        f"{worst_period_points_for}-{worst_period_points_against} "
        f"({worst_period_plus_minus:+d})."
    )
    print(
        f"3. The strongest lineup finished "
        f"{best_lineup_plus_minus:+d} in "
        f"{float(best_lineup_minutes):.2f} minutes."
    )

    if boundary_points:
        print(
            "4. Review boundary-tagged possessions before treating "
            "individual lineup plus-minus as exact."
        )


def print_stretches(
    stretches: list[tuple],
) -> None:
    """Print formatted rotation stretches."""

    if not stretches:
        print("No stretches matched the minimum-duration filter.")
        return

    for stretch_number, stretch in enumerate(
        stretches,
        start=1,
    ):
        (
            period,
            start_deciseconds,
            end_deciseconds,
            duration_seconds,
            lineup_names,
            points_for,
            points_against,
            plus_minus,
        ) = stretch

        start_clock = format_game_clock(
            period,
            start_deciseconds,
        )
        end_clock = format_game_clock(
            period,
            end_deciseconds,
        )

        print(
            f"{stretch_number}. {start_clock} to {end_clock} | "
            f"{float(duration_seconds):.1f} seconds | "
            f"{points_for}-{points_against} "
            f"({plus_minus:+d})"
        )
        print(f"   {lineup_names}")


if __name__ == "__main__":
    main()
