"""Display player box-score data coverage."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def main() -> None:
    """Print overall and team-level box-score coverage."""

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
            FROM marts.box_score_coverage_summary
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
            FROM marts.team_box_score_coverage
            ORDER BY
                coverage_percentage DESC,
                team_abbreviation
            """
        ).fetchall()
    finally:
        connection.close()

    if summary is None:
        print("No box-score coverage information is available.")
        return

    (
        total_games,
        complete_games,
        incomplete_games,
        missing_games,
        coverage_percentage,
    ) = summary

    print(f"Database: {DATABASE_PATH}")
    print("\nOverall box-score coverage:")
    print(f"  Total games: {total_games:,}")
    print(f"  Complete games: {complete_games:,}")
    print(f"  Incomplete games: {incomplete_games:,}")
    print(f"  Missing games: {missing_games:,}")
    print(f"  Coverage: {float(coverage_percentage):.2f}%")

    print("\nTeam coverage:")

    for team_row in team_rows:
        (
            team_abbreviation,
            covered_games,
            total_team_games,
            missing_team_games,
            team_coverage_percentage,
        ) = team_row

        print(
            f"  {team_abbreviation}: "
            f"{covered_games}/{total_team_games} games "
            f"({float(team_coverage_percentage):.2f}%), "
            f"{missing_team_games} missing"
        )


if __name__ == "__main__":
    main()
