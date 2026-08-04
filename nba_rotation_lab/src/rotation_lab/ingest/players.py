"""NBA player reference-data ingestion."""

from pathlib import Path

import pandas as pd
from nba_api.stats.static import players as nba_players

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database

PLAYER_COLUMNS = [
    "player_id",
    "full_name",
    "first_name",
    "last_name",
    "is_active",
]


def fetch_players() -> pd.DataFrame:
    """Return NBA player reference data."""

    records = nba_players.get_players()
    frame = pd.DataFrame.from_records(records)

    return (
        frame.rename(columns={"id": "player_id"})[PLAYER_COLUMNS]
        .sort_values("player_id")
        .reset_index(drop=True)
    )


def load_players(
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
) -> int:
    """Upsert NBA player reference data into DuckDB."""

    players_frame = fetch_players() if frame is None else frame.copy()

    missing_columns = set(PLAYER_COLUMNS).difference(players_frame.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Player data is missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register("players_frame", players_frame)

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.players (
                player_id,
                full_name,
                first_name,
                last_name,
                is_active,
                source_updated_at
            )
            SELECT
                CAST(player_id AS BIGINT),
                full_name,
                first_name,
                last_name,
                CAST(is_active AS BOOLEAN),
                CURRENT_TIMESTAMP
            FROM players_frame
            """
        )
    finally:
        connection.close()

    return len(players_frame)
