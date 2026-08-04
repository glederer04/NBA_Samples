"""Display NBA play-by-play data coverage."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def main() -> None:
    """Print overall and team-level play-by-play coverage."""

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
                missing_games,
                coverage_percentage
            FROM marts.play_by_play_coverage_summary
            """
        ).fetchone()

        team_rows = connection.execute(
            """
            SELECT
                team_abbreviation,
                complete_games,
                total_games,
                incomplete_games,
                missing_games,
                coverage_percentage
            FROM marts.team_play_by_play_coverage
            ORDER BY
                coverage_percentage DESC,
                team_abbreviation
            """
        ).fetchall()
    finally:
        connection.close()

    if summary is None:
        print("No play-by-play coverage information is available.")
        return

    (
        total_games,
        complete_games,
        incomplete_games,
        missing_games,
        coverage_percentage,
    ) = summary

    print(f"Database: {DATABASE_PATH}")
    print("\nOverall play-by-play coverage:")
    print(f"  Total games: {total_games:,}")
    print(f"  Complete games: {complete_games:,}")
    print(f"  Incomplete games: {incomplete_games:,}")
    print(f"  Missing games: {missing_games:,}")
    print(f"  Coverage: {float(coverage_percentage):.2f}%")

    print("\nTeam play-by-play coverage:")

    for row in team_rows:
        (
            team_abbreviation,
            team_complete_games,
            team_total_games,
            team_incomplete_games,
            team_missing_games,
            team_percentage,
        ) = row

        print(
            f"  {team_abbreviation}: "
            f"{team_complete_games}/{team_total_games} complete "
            f"({float(team_percentage):.2f}%), "
            f"{team_incomplete_games} incomplete, "
            f"{team_missing_games} missing"
        )


if __name__ == "__main__":
    main()
