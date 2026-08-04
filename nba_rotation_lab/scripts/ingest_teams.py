"""Load NBA team reference data into DuckDB."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.ingest.teams import load_teams


def main() -> None:
    """Run team reference-data ingestion."""

    row_count = load_teams()

    print(f"Loaded {row_count} NBA teams")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
