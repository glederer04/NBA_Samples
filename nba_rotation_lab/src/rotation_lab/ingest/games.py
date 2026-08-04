"""NBA game-level ingestion."""

from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database
from rotation_lab.ingest.config import (
    DEFAULT_SEASON,
    DEFAULT_SEASON_TYPE,
    NBA_API_TIMEOUT_SECONDS,
)

GAME_COLUMNS = [
    "game_id",
    "season_id",
    "game_date",
    "season_type",
    "home_team_id",
    "away_team_id",
    "home_team_abbreviation",
    "away_team_abbreviation",
    "home_score",
    "away_score",
    "game_status",
]

REQUIRED_TEAM_GAME_COLUMNS = {
    "GAME_ID",
    "SEASON_ID",
    "GAME_DATE",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "MATCHUP",
    "PTS",
}


def parse_matchup(matchup: str) -> tuple[str, str]:
    """Return the home and away abbreviations from an NBA matchup label."""

    if " vs. " in matchup:
        home_abbreviation, away_abbreviation = matchup.split(" vs. ", maxsplit=1)
    elif " @ " in matchup:
        away_abbreviation, home_abbreviation = matchup.split(" @ ", maxsplit=1)
    else:
        raise ValueError(f"Unsupported NBA matchup format: {matchup}")

    return home_abbreviation.strip(), away_abbreviation.strip()


def normalize_games(
    team_games: pd.DataFrame,
    season_type: str,
) -> pd.DataFrame:
    """Convert two team-level records into one record per game."""

    missing_columns = REQUIRED_TEAM_GAME_COLUMNS.difference(team_games.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Team-game data is missing required columns: {missing}")

    frame = team_games.copy()
    frame["GAME_ID"] = frame["GAME_ID"].astype(str)
    frame["SEASON_ID"] = frame["SEASON_ID"].astype(str)

    matchup_teams = pd.DataFrame(
        frame["MATCHUP"].map(parse_matchup).tolist(),
        columns=["_home_abbreviation", "_away_abbreviation"],
        index=frame.index,
    )
    frame = frame.join(matchup_teams)

    home_mask = frame["TEAM_ABBREVIATION"].eq(frame["_home_abbreviation"])
    away_mask = frame["TEAM_ABBREVIATION"].eq(frame["_away_abbreviation"])

    unmatched_rows = frame.loc[
        ~(home_mask | away_mask),
        ["GAME_ID", "TEAM_ABBREVIATION", "MATCHUP"],
    ]

    if not unmatched_rows.empty:
        raise ValueError(
            "Team abbreviation does not match its matchup label: "
            f"{unmatched_rows.to_dict(orient='records')}"
        )

    home_games = frame.loc[
        home_mask,
        [
            "GAME_ID",
            "SEASON_ID",
            "GAME_DATE",
            "TEAM_ID",
            "TEAM_ABBREVIATION",
            "PTS",
        ],
    ].rename(
        columns={
            "GAME_ID": "game_id",
            "SEASON_ID": "season_id",
            "GAME_DATE": "game_date",
            "TEAM_ID": "home_team_id",
            "TEAM_ABBREVIATION": "home_team_abbreviation",
            "PTS": "home_score",
        }
    )

    away_games = frame.loc[
        away_mask,
        [
            "GAME_ID",
            "TEAM_ID",
            "TEAM_ABBREVIATION",
            "PTS",
        ],
    ].rename(
        columns={
            "GAME_ID": "game_id",
            "TEAM_ID": "away_team_id",
            "TEAM_ABBREVIATION": "away_team_abbreviation",
            "PTS": "away_score",
        }
    )

    home_game_ids = set(home_games["game_id"])
    away_game_ids = set(away_games["game_id"])

    if home_game_ids != away_game_ids:
        raise ValueError("Every game must contain one home and one away record")

    games = home_games.merge(
        away_games,
        on="game_id",
        how="inner",
        validate="one_to_one",
    )

    games["game_date"] = pd.to_datetime(games["game_date"]).dt.date
    games["season_type"] = season_type
    games["game_status"] = "Final"

    return (
        games[GAME_COLUMNS]
        .sort_values(
            ["game_date", "game_id"],
        )
        .reset_index(drop=True)
    )


def fetch_games(
    season: str = DEFAULT_SEASON,
    season_type: str = DEFAULT_SEASON_TYPE,
) -> pd.DataFrame:
    """Retrieve and normalize one NBA season of completed games."""

    response = leaguegamefinder.LeagueGameFinder(
        player_or_team_abbreviation="T",
        league_id_nullable="00",
        season_nullable=season,
        season_type_nullable=season_type,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )

    team_games = response.get_data_frames()[0]

    return normalize_games(
        team_games=team_games,
        season_type=season_type,
    )


def load_games(
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
    season: str = DEFAULT_SEASON,
    season_type: str = DEFAULT_SEASON_TYPE,
) -> int:
    """Upsert NBA games into DuckDB."""

    games_frame = (
        fetch_games(season=season, season_type=season_type) if frame is None else frame.copy()
    )

    missing_columns = set(GAME_COLUMNS).difference(games_frame.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Game data is missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register("games_frame", games_frame)

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.games (
                game_id,
                season_id,
                game_date,
                season_type,
                home_team_id,
                away_team_id,
                home_team_abbreviation,
                away_team_abbreviation,
                home_score,
                away_score,
                game_status,
                source_updated_at
            )
            SELECT
                CAST(game_id AS VARCHAR),
                CAST(season_id AS VARCHAR),
                CAST(game_date AS DATE),
                season_type,
                CAST(home_team_id AS BIGINT),
                CAST(away_team_id AS BIGINT),
                home_team_abbreviation,
                away_team_abbreviation,
                CAST(home_score AS INTEGER),
                CAST(away_score AS INTEGER),
                game_status,
                CURRENT_TIMESTAMP
            FROM games_frame
            """
        )
    finally:
        connection.close()

    return len(games_frame)
