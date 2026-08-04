"""NBA team reference-data ingestion."""

from pathlib import Path

import pandas as pd
from nba_api.stats.static import teams as nba_teams

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database

TEAM_COLUMNS = [
    "team_id",
    "abbreviation",
    "team_name",
    "city",
    "state",
    "year_founded",
]


def fetch_teams() -> pd.DataFrame:
    """Return current NBA team reference data."""

    records = nba_teams.get_teams()
    frame = pd.DataFrame.from_records(records)

    return (
        frame.rename(
            columns={
                "id": "team_id",
                "full_name": "team_name",
            }
        )[TEAM_COLUMNS]
        .sort_values("team_id")
        .reset_index(drop=True)
    )


def load_teams(
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
) -> int:
    """Upsert NBA team reference data into DuckDB."""

    teams_frame = fetch_teams() if frame is None else frame.copy()

    missing_columns = set(TEAM_COLUMNS).difference(teams_frame.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Team data is missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register("teams_frame", teams_frame)

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.teams (
                team_id,
                abbreviation,
                team_name,
                city,
                state,
                year_founded,
                source_updated_at
            )
            SELECT
                CAST(team_id AS BIGINT),
                abbreviation,
                team_name,
                city,
                state,
                CAST(year_founded AS INTEGER),
                CURRENT_TIMESTAMP
            FROM teams_frame
            """
        )
    finally:
        connection.close()

    return len(teams_frame)
