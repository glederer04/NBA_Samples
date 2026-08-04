"""Initialize DuckDB and load NBA reference data."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import initialize_database
from rotation_lab.ingest.players import load_players
from rotation_lab.ingest.teams import load_teams


def main() -> None:
    """Run the complete NBA reference-data pipeline."""

    executed_files = initialize_database()
    team_count = load_teams()
    player_count = load_players()

    print("NBA reference-data pipeline completed")
    print(f"Database: {DATABASE_PATH}")
    print(f"SQL files executed: {len(executed_files)}")
    print(f"Teams loaded: {team_count}")
    print(f"Players loaded: {player_count}")


if __name__ == "__main__":
    main()
