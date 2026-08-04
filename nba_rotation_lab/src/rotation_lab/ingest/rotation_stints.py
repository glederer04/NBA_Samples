"""NBA player rotation-stint ingestion."""

from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import gamerotation
from nba_api.stats.library.http import NBAStatsHTTP

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database
from rotation_lab.ingest.config import NBA_API_TIMEOUT_SECONDS

ROTATION_STINT_COLUMNS = [
    "game_id",
    "team_id",
    "player_id",
    "stint_number",
    "team_location",
    "team_city",
    "team_name",
    "player_name",
    "period",
    "in_time_deciseconds",
    "out_time_deciseconds",
    "in_time_seconds",
    "out_time_seconds",
    "duration_seconds",
    "player_points",
    "point_differential",
    "usage_percentage",
]

REQUIRED_ROTATION_COLUMNS = {
    "GAME_ID",
    "TEAM_ID",
    "TEAM_CITY",
    "TEAM_NAME",
    "PERSON_ID",
    "PLAYER_FIRST",
    "PLAYER_LAST",
    "IN_TIME_REAL",
    "OUT_TIME_REAL",
    "PLAYER_PTS",
    "PT_DIFF",
    "USG_PCT",
}


class RotationDataUnavailableError(RuntimeError):
    """Raised when NBA Stats returns no rotation payload for a game."""


def calculate_period(in_time_deciseconds: int) -> int:
    """Return the NBA period for a game-elapsed time value."""

    regulation_period_length = 7200
    overtime_period_length = 3000
    regulation_game_length = regulation_period_length * 4

    if in_time_deciseconds < regulation_game_length:
        return in_time_deciseconds // regulation_period_length + 1

    overtime_elapsed = in_time_deciseconds - regulation_game_length

    return overtime_elapsed // overtime_period_length + 5


def normalize_rotation_stints(
    away_team: pd.DataFrame,
    home_team: pd.DataFrame,
) -> pd.DataFrame:
    """Combine and normalize home and away rotation records."""

    for frame_name, frame in [
        ("away", away_team),
        ("home", home_team),
    ]:
        missing_columns = REQUIRED_ROTATION_COLUMNS.difference(frame.columns)

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))

            raise ValueError(
                f"{frame_name.title()} rotation data is missing required columns: {missing}"
            )

    away_frame = away_team.copy()
    home_frame = home_team.copy()

    away_frame["team_location"] = "away"
    home_frame["team_location"] = "home"

    frame = pd.concat(
        [
            away_frame,
            home_frame,
        ],
        ignore_index=True,
    )

    frame["game_id"] = frame["GAME_ID"].astype(str)
    frame["team_id"] = pd.to_numeric(frame["TEAM_ID"]).astype("int64")
    frame["player_id"] = pd.to_numeric(frame["PERSON_ID"]).astype("int64")

    first_names = frame["PLAYER_FIRST"].fillna("").astype(str).str.strip()
    last_names = frame["PLAYER_LAST"].fillna("").astype(str).str.strip()

    frame["player_name"] = first_names.str.cat(last_names, sep=" ").str.strip()
    frame["team_city"] = frame["TEAM_CITY"].fillna("").astype(str).str.strip()
    frame["team_name"] = frame["TEAM_NAME"].fillna("").astype(str).str.strip()

    frame["in_time_deciseconds"] = pd.to_numeric(frame["IN_TIME_REAL"]).round().astype("int64")
    frame["out_time_deciseconds"] = pd.to_numeric(frame["OUT_TIME_REAL"]).round().astype("int64")

    invalid_times = frame.loc[
        frame["out_time_deciseconds"] < frame["in_time_deciseconds"],
        [
            "game_id",
            "player_id",
            "in_time_deciseconds",
            "out_time_deciseconds",
        ],
    ]

    if not invalid_times.empty:
        raise ValueError(
            f"Rotation stints must end after they begin: {invalid_times.to_dict(orient='records')}"
        )

    frame = frame.loc[frame["out_time_deciseconds"] > frame["in_time_deciseconds"]].copy()

    frame["in_time_seconds"] = frame["in_time_deciseconds"] / 10
    frame["out_time_seconds"] = frame["out_time_deciseconds"] / 10
    frame["duration_seconds"] = (frame["out_time_seconds"] - frame["in_time_seconds"]).round(1)

    frame["period"] = frame["in_time_deciseconds"].map(calculate_period)
    frame["player_points"] = pd.to_numeric(
        frame["PLAYER_PTS"],
        errors="coerce",
    )
    frame["point_differential"] = pd.to_numeric(
        frame["PT_DIFF"],
        errors="coerce",
    )
    frame["usage_percentage"] = pd.to_numeric(
        frame["USG_PCT"],
        errors="coerce",
    )

    frame = frame.sort_values(
        [
            "game_id",
            "team_id",
            "player_id",
            "in_time_deciseconds",
            "out_time_deciseconds",
        ]
    ).reset_index(drop=True)

    frame["stint_number"] = (
        frame.groupby(
            [
                "game_id",
                "team_id",
                "player_id",
            ]
        )
        .cumcount()
        .add(1)
    )

    return frame[ROTATION_STINT_COLUMNS]


def fetch_rotation_stints(game_id: str) -> pd.DataFrame:
    """Retrieve and normalize one NBA game's rotation stints."""

    response = gamerotation.GameRotation(
        game_id=game_id,
        league_id="00",
        timeout=NBA_API_TIMEOUT_SECONDS,
        get_request=False,
    )

    nba_response = NBAStatsHTTP().send_api_request(
        endpoint=response.endpoint,
        parameters=response.parameters,
        proxy=response.proxy,
        headers=response.headers,
        timeout=response.timeout,
    )
    response_body = nba_response.get_response()

    if not response_body.strip():
        raise RotationDataUnavailableError(
            f"NBA Stats returned an empty rotation response for game {game_id}"
        )

    if not nba_response.valid_json():
        raise RuntimeError(f"NBA Stats returned an invalid rotation response for game {game_id}")

    response.nba_response = nba_response
    response.load_response()

    away_team, home_team = response.get_data_frames()

    return normalize_rotation_stints(
        away_team=away_team,
        home_team=home_team,
    )


def load_rotation_stints(
    game_id: str | None = None,
    database_path: Path = DATABASE_PATH,
    frame: pd.DataFrame | None = None,
) -> int:
    """Upsert player rotation stints into DuckDB."""

    if frame is None:
        if game_id is None:
            raise ValueError("game_id is required when frame is not provided")

        rotation_stints = fetch_rotation_stints(game_id)
    else:
        rotation_stints = frame.copy()

    missing_columns = set(ROTATION_STINT_COLUMNS).difference(rotation_stints.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Rotation stints are missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.register(
            "rotation_stints_frame",
            rotation_stints,
        )

        connection.execute(
            """
            INSERT OR REPLACE INTO raw.rotation_stints (
                game_id,
                team_id,
                player_id,
                stint_number,
                team_location,
                team_city,
                team_name,
                player_name,
                period,
                in_time_deciseconds,
                out_time_deciseconds,
                in_time_seconds,
                out_time_seconds,
                duration_seconds,
                player_points,
                point_differential,
                usage_percentage,
                source_updated_at
            )
            SELECT
                CAST(game_id AS VARCHAR),
                CAST(team_id AS BIGINT),
                CAST(player_id AS BIGINT),
                CAST(stint_number AS INTEGER),
                team_location,
                team_city,
                team_name,
                player_name,
                CAST(period AS INTEGER),
                CAST(in_time_deciseconds AS BIGINT),
                CAST(out_time_deciseconds AS BIGINT),
                CAST(in_time_seconds AS DOUBLE),
                CAST(out_time_seconds AS DOUBLE),
                CAST(duration_seconds AS DOUBLE),
                CAST(player_points AS INTEGER),
                CAST(point_differential AS DOUBLE),
                CAST(usage_percentage AS DOUBLE),
                CURRENT_TIMESTAMP
            FROM rotation_stints_frame
            """
        )
    finally:
        connection.close()

    return len(rotation_stints)
