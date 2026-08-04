"""NBA traditional player box-score ingestion."""

from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv3

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database
from rotation_lab.ingest.config import NBA_API_TIMEOUT_SECONDS

PLAYER_BOX_SCORE_COLUMNS = [
    "game_id",
    "team_id",
    "player_id",
    "team_abbreviation",
    "player_name",
    "position",
    "comment",
    "minutes",
    "starter",
    "did_not_play",
    "field_goals_made",
    "field_goals_attempted",
    "field_goal_percentage",
    "three_pointers_made",
    "three_pointers_attempted",
    "three_point_percentage",
    "free_throws_made",
    "free_throws_attempted",
    "free_throw_percentage",
    "offensive_rebounds",
    "defensive_rebounds",
    "total_rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "personal_fouls",
    "points",
    "plus_minus",
]

SOURCE_COLUMN_MAP = {
    "gameId": "game_id",
    "teamId": "team_id",
    "teamTricode": "team_abbreviation",
    "personId": "player_id",
    "position": "position",
    "comment": "comment",
    "minutes": "minutes",
    "fieldGoalsMade": "field_goals_made",
    "fieldGoalsAttempted": "field_goals_attempted",
    "fieldGoalsPercentage": "field_goal_percentage",
    "threePointersMade": "three_pointers_made",
    "threePointersAttempted": "three_pointers_attempted",
    "threePointersPercentage": "three_point_percentage",
    "freeThrowsMade": "free_throws_made",
    "freeThrowsAttempted": "free_throws_attempted",
    "freeThrowsPercentage": "free_throw_percentage",
    "reboundsOffensive": "offensive_rebounds",
    "reboundsDefensive": "defensive_rebounds",
    "reboundsTotal": "total_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "foulsPersonal": "personal_fouls",
    "points": "points",
    "plusMinusPoints": "plus_minus",
}

REQUIRED_SOURCE_COLUMNS = {
    *SOURCE_COLUMN_MAP,
    "firstName",
    "familyName",
}

NUMERIC_COLUMNS = [
    "field_goals_made",
    "field_goals_attempted",
    "field_goal_percentage",
    "three_pointers_made",
    "three_pointers_attempted",
    "three_point_percentage",
    "free_throws_made",
    "free_throws_attempted",
    "free_throw_percentage",
    "offensive_rebounds",
    "defensive_rebounds",
    "total_rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "personal_fouls",
    "points",
    "plus_minus",
]


def minutes_to_decimal(value: object) -> float | None:
    """Convert an NBA minutes value such as 35:30 to decimal minutes."""

    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"nan", "nat", "none", "<na>"}:
        return None

    if ":" not in text:
        return float(text)

    minute_text, second_text = text.split(":", maxsplit=1)

    return float(minute_text) + float(second_text) / 60


def normalize_player_box_scores(
    player_stats: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize an NBA traditional player box-score response."""

    missing_columns = REQUIRED_SOURCE_COLUMNS.difference(player_stats.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Player box-score data is missing required columns: {missing}")

    frame = player_stats.rename(columns=SOURCE_COLUMN_MAP).copy()

    first_names = frame["firstName"].fillna("").astype(str).str.strip()
    family_names = frame["familyName"].fillna("").astype(str).str.strip()

    frame["player_name"] = first_names.str.cat(family_names, sep=" ").str.strip()
    frame["game_id"] = frame["game_id"].astype(str)
    frame["team_id"] = pd.to_numeric(frame["team_id"]).astype("int64")
    frame["player_id"] = pd.to_numeric(frame["player_id"]).astype("int64")
    frame["position"] = frame["position"].fillna("").astype(str).str.strip()
    frame["comment"] = frame["comment"].fillna("").astype(str).str.strip()
    frame["minutes"] = frame["minutes"].map(minutes_to_decimal)
    frame["starter"] = frame["position"].ne("")
    frame["did_not_play"] = frame["minutes"].isna()

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    return (
        frame[PLAYER_BOX_SCORE_COLUMNS]
        .sort_values(
            ["game_id", "team_id", "starter", "player_id"],
            ascending=[True, True, False, True],
        )
        .reset_index(drop=True)
    )


def fetch_player_box_scores(game_id: str) -> pd.DataFrame:
    """Retrieve and normalize one NBA game's traditional box score."""

    response = boxscoretraditionalv3.BoxScoreTraditionalV3(
        game_id=game_id,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )

    player_stats = response.get_data_frames()[0]

    return normalize_player_box_scores(player_stats)


def load_player_box_scores(
    game_id: str | None = None,
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
) -> int:
    """Upsert player box scores into DuckDB."""

    if frame is None:
        if game_id is None:
            raise ValueError("game_id is required when frame is not provided")

        box_scores = fetch_player_box_scores(game_id)
    else:
        box_scores = frame.copy()

    missing_columns = set(PLAYER_BOX_SCORE_COLUMNS).difference(box_scores.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Player box scores are missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register("player_box_scores_frame", box_scores)

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.player_box_scores (
                game_id,
                team_id,
                player_id,
                team_abbreviation,
                player_name,
                position,
                comment,
                minutes,
                starter,
                did_not_play,
                field_goals_made,
                field_goals_attempted,
                field_goal_percentage,
                three_pointers_made,
                three_pointers_attempted,
                three_point_percentage,
                free_throws_made,
                free_throws_attempted,
                free_throw_percentage,
                offensive_rebounds,
                defensive_rebounds,
                total_rebounds,
                assists,
                steals,
                blocks,
                turnovers,
                personal_fouls,
                points,
                plus_minus,
                source_updated_at
            )
            SELECT
                CAST(game_id AS VARCHAR),
                CAST(team_id AS BIGINT),
                CAST(player_id AS BIGINT),
                team_abbreviation,
                player_name,
                position,
                comment,
                CAST(minutes AS DOUBLE),
                CAST(starter AS BOOLEAN),
                CAST(did_not_play AS BOOLEAN),
                CAST(field_goals_made AS INTEGER),
                CAST(field_goals_attempted AS INTEGER),
                CAST(field_goal_percentage AS DOUBLE),
                CAST(three_pointers_made AS INTEGER),
                CAST(three_pointers_attempted AS INTEGER),
                CAST(three_point_percentage AS DOUBLE),
                CAST(free_throws_made AS INTEGER),
                CAST(free_throws_attempted AS INTEGER),
                CAST(free_throw_percentage AS DOUBLE),
                CAST(offensive_rebounds AS INTEGER),
                CAST(defensive_rebounds AS INTEGER),
                CAST(total_rebounds AS INTEGER),
                CAST(assists AS INTEGER),
                CAST(steals AS INTEGER),
                CAST(blocks AS INTEGER),
                CAST(turnovers AS INTEGER),
                CAST(personal_fouls AS INTEGER),
                CAST(points AS INTEGER),
                CAST(plus_minus AS DOUBLE),
                CURRENT_TIMESTAMP
            FROM player_box_scores_frame
            """
        )
    finally:
        connection.close()

    return len(box_scores)
