"""NBA play-by-play event ingestion."""

import re
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import playbyplayv3

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database
from rotation_lab.ingest.config import NBA_API_TIMEOUT_SECONDS

PLAY_BY_PLAY_COLUMNS = [
    "game_id",
    "action_id",
    "action_number",
    "period",
    "clock",
    "clock_seconds_remaining",
    "game_elapsed_deciseconds",
    "team_id",
    "team_abbreviation",
    "player_id",
    "player_name",
    "location",
    "action_type",
    "sub_type",
    "description",
    "shot_result",
    "is_field_goal",
    "shot_value",
    "score_home",
    "score_away",
    "points_total",
    "video_available",
]

SOURCE_COLUMN_MAP = {
    "gameId": "game_id",
    "actionId": "action_id",
    "actionNumber": "action_number",
    "period": "period",
    "clock": "clock",
    "teamId": "team_id",
    "teamTricode": "team_abbreviation",
    "personId": "player_id",
    "playerName": "player_name",
    "location": "location",
    "actionType": "action_type",
    "subType": "sub_type",
    "description": "description",
    "shotResult": "shot_result",
    "isFieldGoal": "is_field_goal",
    "shotValue": "shot_value",
    "scoreHome": "score_home",
    "scoreAway": "score_away",
    "pointsTotal": "points_total",
    "videoAvailable": "video_available",
}

REQUIRED_SOURCE_COLUMNS = set(SOURCE_COLUMN_MAP)

CLOCK_PATTERN = re.compile(r"^PT(?P<minutes>\d+)M(?P<seconds>\d+(?:\.\d+)?)S$")


def parse_clock_seconds(clock: object) -> float:
    """Convert an NBA ISO clock value into seconds remaining."""

    text = str(clock).strip()
    match = CLOCK_PATTERN.fullmatch(text)

    if match is None:
        raise ValueError(f"Unsupported NBA game clock: {text}")

    minutes = int(match.group("minutes"))
    seconds = float(match.group("seconds"))

    return minutes * 60 + seconds


def calculate_game_elapsed_deciseconds(
    period: int,
    clock_seconds_remaining: float,
) -> int:
    """Calculate game-elapsed deciseconds for an NBA event."""

    if period < 1:
        raise ValueError("NBA periods must be greater than zero")

    if period <= 4:
        period_length_seconds = 720
        period_start_seconds = (period - 1) * 720
    else:
        period_length_seconds = 300
        period_start_seconds = 2880 + (period - 5) * 300

    if not 0 <= clock_seconds_remaining <= period_length_seconds:
        raise ValueError(
            "Clock seconds must be within the current period: "
            f"period={period}, seconds={clock_seconds_remaining}"
        )

    elapsed_seconds = period_start_seconds + period_length_seconds - clock_seconds_remaining

    return round(elapsed_seconds * 10)


def normalize_play_by_play(events: pd.DataFrame) -> pd.DataFrame:
    """Normalize one NBA play-by-play response."""

    missing_columns = REQUIRED_SOURCE_COLUMNS.difference(events.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Play-by-play data is missing required columns: {missing}")

    frame = events.rename(columns=SOURCE_COLUMN_MAP).copy()

    frame["game_id"] = frame["game_id"].astype(str)
    frame["action_id"] = pd.to_numeric(frame["action_id"]).astype("int64")
    frame["action_number"] = pd.to_numeric(frame["action_number"]).astype("int64")
    frame["period"] = pd.to_numeric(frame["period"]).astype("int64")

    frame["clock"] = frame["clock"].astype(str).str.strip()
    frame["clock_seconds_remaining"] = frame["clock"].map(parse_clock_seconds)

    frame["game_elapsed_deciseconds"] = [
        calculate_game_elapsed_deciseconds(
            period=int(period),
            clock_seconds_remaining=float(clock_seconds),
        )
        for period, clock_seconds in zip(
            frame["period"],
            frame["clock_seconds_remaining"],
            strict=True,
        )
    ]

    frame["team_id"] = (
        pd.to_numeric(
            frame["team_id"],
            errors="coerce",
        )
        .mask(lambda values: values.eq(0))
        .astype("Int64")
    )
    frame["player_id"] = (
        pd.to_numeric(
            frame["player_id"],
            errors="coerce",
        )
        .mask(lambda values: values.eq(0))
        .astype("Int64")
    )

    text_columns = [
        "team_abbreviation",
        "player_name",
        "location",
        "action_type",
        "sub_type",
        "description",
        "shot_result",
    ]

    for column in text_columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    integer_columns = [
        "shot_value",
        "score_home",
        "score_away",
        "points_total",
    ]

    for column in integer_columns:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        ).astype("Int64")

    frame["is_field_goal"] = (
        pd.to_numeric(
            frame["is_field_goal"],
            errors="coerce",
        )
        .fillna(0)
        .astype("int64")
        .astype(bool)
    )
    frame["video_available"] = (
        pd.to_numeric(
            frame["video_available"],
            errors="coerce",
        )
        .fillna(0)
        .astype("int64")
        .astype(bool)
    )

    return (
        frame[PLAY_BY_PLAY_COLUMNS]
        .sort_values(
            [
                "game_id",
                "game_elapsed_deciseconds",
                "action_number",
                "action_id",
            ]
        )
        .reset_index(drop=True)
    )


def fetch_play_by_play(game_id: str) -> pd.DataFrame:
    """Retrieve and normalize one NBA game's play-by-play events."""

    response = playbyplayv3.PlayByPlayV3(
        game_id=game_id,
        timeout=NBA_API_TIMEOUT_SECONDS,
    )

    events = response.get_data_frames()[0]

    return normalize_play_by_play(events)


def load_play_by_play(
    game_id: str | None = None,
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
) -> int:
    """Upsert one game's play-by-play events into DuckDB."""

    if frame is None:
        if game_id is None:
            raise ValueError("game_id is required when frame is not provided")

        play_by_play = fetch_play_by_play(game_id)
    else:
        play_by_play = frame.copy()

    missing_columns = set(PLAY_BY_PLAY_COLUMNS).difference(play_by_play.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Play-by-play events are missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register(
            "play_by_play_frame",
            play_by_play,
        )

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.play_by_play_events (
                game_id,
                action_id,
                action_number,
                period,
                clock,
                clock_seconds_remaining,
                game_elapsed_deciseconds,
                team_id,
                team_abbreviation,
                player_id,
                player_name,
                location,
                action_type,
                sub_type,
                description,
                shot_result,
                is_field_goal,
                shot_value,
                score_home,
                score_away,
                points_total,
                video_available,
                source_updated_at
            )
            SELECT
                CAST(game_id AS VARCHAR),
                CAST(action_id AS INTEGER),
                CAST(action_number AS INTEGER),
                CAST(period AS INTEGER),
                clock,
                CAST(clock_seconds_remaining AS DOUBLE),
                CAST(game_elapsed_deciseconds AS BIGINT),
                CAST(team_id AS BIGINT),
                team_abbreviation,
                CAST(player_id AS BIGINT),
                player_name,
                location,
                action_type,
                sub_type,
                description,
                shot_result,
                CAST(is_field_goal AS BOOLEAN),
                CAST(shot_value AS INTEGER),
                CAST(score_home AS INTEGER),
                CAST(score_away AS INTEGER),
                CAST(points_total AS INTEGER),
                CAST(video_available AS BOOLEAN),
                CURRENT_TIMESTAMP
            FROM play_by_play_frame
            """
        )
    finally:
        connection.close()

    return len(play_by_play)
