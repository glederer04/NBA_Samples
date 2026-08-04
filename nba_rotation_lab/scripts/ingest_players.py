"""Load NBA player reference data into DuckDB."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.ingest.players import load_players


def main() -> None:
    """Run player reference-data ingestion."""

    row_count = load_players()

    print(f"Loaded {row_count} NBA players")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
