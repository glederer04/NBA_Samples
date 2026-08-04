"""Display NBA rotation-stint data coverage."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def main() -> None:
    """Print overall and team-level rotation coverage."""

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
            FROM marts.rotation_coverage_summary
            """
        ).fetchone()

        team_rows = connection.execute(
            """
            SELECT
                team_abbreviation,
                covered_games,
                total_games,
                missing_games,
                coverage_percentage
            FROM marts.team_rotation_coverage
            ORDER BY
                coverage_percentage DESC,
                team_abbreviation
            """
        ).fetchall()
    finally:
        connection.close()

    if summary is None:
        print("No rotation coverage information is available.")
        return

    (
        total_games,
        complete_games,
        incomplete_games,
        missing_games,
        coverage_percentage,
    ) = summary

    print(f"Database: {DATABASE_PATH}")
    print("\nOverall rotation coverage:")
    print(f"  Total games: {total_games:,}")
    print(f"  Complete games: {complete_games:,}")
    print(f"  Incomplete games: {incomplete_games:,}")
    print(f"  Missing games: {missing_games:,}")
    print(f"  Coverage: {float(coverage_percentage):.2f}%")

    print("\nTeam rotation coverage:")

    for row in team_rows:
        (
            team_abbreviation,
            covered_games,
            total_team_games,
            missing_team_games,
            team_percentage,
        ) = row

        print(
            f"  {team_abbreviation}: "
            f"{covered_games}/{total_team_games} games "
            f"({float(team_percentage):.2f}%), "
            f"{missing_team_games} missing"
        )


if __name__ == "__main__":
    main()
