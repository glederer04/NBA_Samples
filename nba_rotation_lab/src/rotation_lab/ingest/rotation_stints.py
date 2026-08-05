"""NBA player rotation-stint ingestion."""

import re
import unicodedata
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


SUBSTITUTION_PATTERN = re.compile(
    r"^SUB:\s*(?P<incoming>.+?)\s+FOR\s+.+$",
    flags=re.IGNORECASE,
)


def normalize_player_label(value: object) -> str:
    """Normalize NBA player labels for substitution-name matching."""

    text = unicodedata.normalize("NFKD", str(value))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")

    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).split())


def player_label_match_score(player_name: object, incoming_label: object) -> int:
    """Score full, shortened, abbreviated, and reordered NBA player labels."""

    normalized_name = normalize_player_label(player_name)
    normalized_label = normalize_player_label(incoming_label)
    name_parts = normalized_name.split()
    label_parts = normalized_label.split()

    if not label_parts:
        return 0

    if normalized_name == normalized_label:
        return 10

    if len(label_parts) <= len(name_parts):
        window_scores = []

        for start in range(len(name_parts) - len(label_parts) + 1):
            name_window = name_parts[start : start + len(label_parts)]

            if all(
                name_part.startswith(label_part)
                for name_part, label_part in zip(name_window, label_parts, strict=True)
            ):
                window_scores.append(9 if start + len(label_parts) == len(name_parts) else 7)

        if window_scores:
            return max(window_scores)

    if len(label_parts) == 1 and normalized_label in name_parts:
        return 8 if name_parts[-1] == normalized_label else 6

    return 0


def match_incoming_player(
    team_players: pd.DataFrame,
    incoming_label: str,
    active_player_ids: set[int],
) -> pd.Series:
    """Match a substitution description to one inactive box-score player."""

    normalized_label = normalize_player_label(incoming_label)
    candidates: list[tuple[int, pd.Series]] = []

    for _, player in team_players.iterrows():
        player_id = int(player["player_id"])

        if player_id in active_player_ids or bool(player["did_not_play"]):
            continue

        score = player_label_match_score(
            player_name=player["player_name"],
            incoming_label=normalized_label,
        )

        if score:
            candidates.append((score, player))

    if not candidates:
        raise ValueError(f"No inactive player matches substitution label: {incoming_label}")

    best_score = max(score for score, _ in candidates)
    best_candidates = [player for score, player in candidates if score == best_score]

    if len(best_candidates) != 1:
        names = ", ".join(str(player["player_name"]) for player in best_candidates)
        raise ValueError(f"Ambiguous substitution label {incoming_label!r}; candidates: {names}")

    return best_candidates[0]


def validate_rotation_minutes(
    rotation_stints: pd.DataFrame,
    box_scores: pd.DataFrame,
    tolerance_minutes: float = 0.02,
) -> None:
    """Require rotation totals to agree with official player minutes."""

    rotation_minutes = rotation_stints.groupby("player_id")["duration_seconds"].sum() / 60
    official_minutes = (
        box_scores.loc[~box_scores["did_not_play"].astype(bool)]
        .set_index("player_id")["minutes"]
        .astype(float)
    )
    minute_differences = {
        int(player_id): abs(float(minutes) - float(rotation_minutes.get(int(player_id), 0.0)))
        for player_id, minutes in official_minutes.items()
    }
    inaccurate_players = {
        player_id: difference
        for player_id, difference in minute_differences.items()
        if difference > tolerance_minutes
    }

    if inaccurate_players:
        raise ValueError(
            f"Rotation minutes do not match the official box score: {inaccurate_players}"
        )


def reconstruct_rotation_stints(
    game_id: str,
    play_by_play: pd.DataFrame,
    box_scores: pd.DataFrame,
) -> pd.DataFrame:
    """Reconstruct player stints from starters and substitution events."""

    required_event_columns = {
        "action_number",
        "action_type",
        "description",
        "game_elapsed_deciseconds",
        "period",
        "player_id",
        "team_id",
    }
    required_box_score_columns = {
        "did_not_play",
        "minutes",
        "player_id",
        "player_name",
        "starter",
        "team_city",
        "team_id",
        "team_location",
        "team_name",
    }

    missing_event_columns = required_event_columns.difference(play_by_play.columns)
    missing_box_score_columns = required_box_score_columns.difference(box_scores.columns)

    if missing_event_columns:
        missing = ", ".join(sorted(missing_event_columns))
        raise ValueError(f"Play-by-play fallback is missing columns: {missing}")

    if missing_box_score_columns:
        missing = ", ".join(sorted(missing_box_score_columns))
        raise ValueError(f"Box-score fallback is missing columns: {missing}")

    maximum_period = int(play_by_play["period"].max())
    game_length_deciseconds = 28800 + max(maximum_period - 4, 0) * 3000
    stint_rows: list[dict[str, object]] = []

    substitutions = play_by_play.loc[
        play_by_play["action_type"].astype(str).str.casefold().eq("substitution")
    ].sort_values(
        ["game_elapsed_deciseconds", "action_number"],
    )

    for team_id_value, team_players in box_scores.groupby("team_id"):
        team_id = int(team_id_value)
        player_lookup = {int(player["player_id"]): player for _, player in team_players.iterrows()}
        team_events = play_by_play.loc[
            play_by_play["team_id"].fillna(0).astype("int64").eq(team_id)
        ]

        for period in range(1, maximum_period + 1):
            if period <= 4:
                period_start = (period - 1) * 7200
                period_end = period * 7200
            else:
                period_start = 28800 + (period - 5) * 3000
                period_end = period_start + 3000

            period_events = team_events.loc[team_events["period"].eq(period)]
            period_substitutions = substitutions.loc[
                substitutions["period"].eq(period)
                & substitutions["team_id"].fillna(0).astype("int64").eq(team_id)
            ]
            resolved_substitutions: list[tuple[pd.Series, int]] = []
            first_substitution_role: dict[int, str] = {}

            for _, substitution in period_substitutions.iterrows():
                outgoing_player_id = int(substitution["player_id"])
                description = str(substitution["description"])
                match = SUBSTITUTION_PATTERN.match(description.strip())

                if match is None:
                    raise ValueError(f"Unsupported substitution description: {description}")

                incoming_player = match_incoming_player(
                    team_players=team_players,
                    incoming_label=match.group("incoming"),
                    active_player_ids=set(),
                )
                incoming_player_id = int(incoming_player["player_id"])
                first_substitution_role.setdefault(outgoing_player_id, "out")
                first_substitution_role.setdefault(incoming_player_id, "in")
                resolved_substitutions.append((substitution, incoming_player_id))

            period_starter_ids = {
                player_id for player_id, role in first_substitution_role.items() if role == "out"
            }

            if len(period_starter_ids) > 5:
                raise ValueError(
                    f"Substitution sequence implies more than five period {period} "
                    f"starters for team {team_id}: {sorted(period_starter_ids)}"
                )

            if len(period_starter_ids) < 5:
                unknown_player_ids = [
                    int(player["player_id"])
                    for _, player in team_players.iterrows()
                    if not bool(player["did_not_play"])
                    and int(player["player_id"]) not in first_substitution_role
                ]
                player_activity = (
                    period_events.loc[
                        period_events["player_id"].notna()
                        & period_events["player_id"].astype("Int64").isin(unknown_player_ids)
                    ]
                    .groupby("player_id")
                    .agg(
                        first_action=("game_elapsed_deciseconds", "min"),
                        action_count=("action_number", "size"),
                    )
                )
                assigned_deciseconds = {
                    player_id: sum(
                        int(row["out_time_deciseconds"]) - int(row["in_time_deciseconds"])
                        for row in stint_rows
                        if int(row["team_id"]) == team_id and int(row["player_id"]) == player_id
                    )
                    for player_id in unknown_player_ids
                }
                official_deciseconds = {
                    int(player["player_id"]): round(float(player["minutes"]) * 600)
                    for _, player in team_players.iterrows()
                    if not bool(player["did_not_play"])
                }
                ranked_unknown_ids = sorted(
                    unknown_player_ids,
                    key=lambda player_id: (
                        player_id not in player_activity.index,
                        int(player_activity.loc[player_id, "first_action"])
                        if player_id in player_activity.index
                        else period_end + 1,
                        -int(player_activity.loc[player_id, "action_count"])
                        if player_id in player_activity.index
                        else 0,
                        -(official_deciseconds[player_id] - assigned_deciseconds[player_id]),
                        player_id,
                    ),
                )
                needed_players = 5 - len(period_starter_ids)
                period_starter_ids.update(ranked_unknown_ids[:needed_players])

            if len(period_starter_ids) != 5:
                raise ValueError(
                    f"Could not infer five period {period} starters for team {team_id}"
                )

            active_starts = {player_id: period_start for player_id in period_starter_ids}

            for substitution, incoming_player_id in resolved_substitutions:
                outgoing_player_id = int(substitution["player_id"])
                substitution_time = int(substitution["game_elapsed_deciseconds"])

                if outgoing_player_id not in active_starts:
                    raise ValueError(
                        f"Outgoing player {outgoing_player_id} is not active in period "
                        f"{period} at {substitution_time} deciseconds"
                    )

                if incoming_player_id in active_starts:
                    raise ValueError(
                        f"Incoming player {incoming_player_id} is already active in period "
                        f"{period} at {substitution_time} deciseconds"
                    )

                outgoing_player = player_lookup[outgoing_player_id]
                stint_start = active_starts.pop(outgoing_player_id)

                if substitution_time > stint_start:
                    stint_rows.append(
                        {
                            "game_id": game_id,
                            "team_id": team_id,
                            "player_id": outgoing_player_id,
                            "team_location": outgoing_player["team_location"],
                            "team_city": outgoing_player["team_city"],
                            "team_name": outgoing_player["team_name"],
                            "player_name": outgoing_player["player_name"],
                            "in_time_deciseconds": stint_start,
                            "out_time_deciseconds": substitution_time,
                        }
                    )

                active_starts[incoming_player_id] = substitution_time

            if len(active_starts) != 5:
                raise ValueError(
                    f"Rotation fallback ended period {period} with "
                    f"{len(active_starts)} active players for team {team_id}"
                )

            for player_id, stint_start in active_starts.items():
                player = player_lookup[player_id]

                if period_end > stint_start:
                    stint_rows.append(
                        {
                            "game_id": game_id,
                            "team_id": team_id,
                            "player_id": player_id,
                            "team_location": player["team_location"],
                            "team_city": player["team_city"],
                            "team_name": player["team_name"],
                            "player_name": player["player_name"],
                            "in_time_deciseconds": stint_start,
                            "out_time_deciseconds": period_end,
                        }
                    )

    frame = pd.DataFrame(stint_rows)

    if frame.empty:
        raise ValueError(f"No rotation stints could be reconstructed for game {game_id}")

    frame["in_time_seconds"] = frame["in_time_deciseconds"] / 10
    frame["out_time_seconds"] = frame["out_time_deciseconds"] / 10
    frame["duration_seconds"] = frame["out_time_seconds"] - frame["in_time_seconds"]
    frame["period"] = frame["in_time_deciseconds"].map(calculate_period)
    frame["player_points"] = None
    frame["point_differential"] = None
    frame["usage_percentage"] = None
    frame = frame.sort_values(
        ["game_id", "team_id", "player_id", "in_time_deciseconds"],
    ).reset_index(drop=True)
    frame["stint_number"] = frame.groupby(["game_id", "team_id", "player_id"]).cumcount().add(1)

    team_duration = frame.groupby("team_id")["duration_seconds"].sum()
    expected_team_duration = game_length_deciseconds / 10 * 5

    if not team_duration.map(lambda value: abs(value - expected_team_duration) < 0.01).all():
        raise ValueError(
            f"Reconstructed rotation duration does not cover five players: "
            f"{team_duration.to_dict()}"
        )

    validate_rotation_minutes(
        rotation_stints=frame,
        box_scores=box_scores,
    )

    return frame[ROTATION_STINT_COLUMNS]


def fetch_local_box_scores(
    game_id: str,
    database_path: Path,
) -> pd.DataFrame:
    """Return the local official box score used to validate rotations."""

    connection = connect_database(database_path, read_only=True)

    try:
        box_scores = connection.execute(
            """
            SELECT
                box_scores.team_id,
                box_scores.player_id,
                box_scores.player_name,
                box_scores.starter,
                box_scores.did_not_play,
                box_scores.minutes,
                CASE
                    WHEN box_scores.team_id = games.home_team_id THEN 'home'
                    ELSE 'away'
                END AS team_location,
                teams.city AS team_city,
                teams.team_name
            FROM raw.player_box_scores AS box_scores
            INNER JOIN raw.games AS games
                ON box_scores.game_id = games.game_id
            LEFT JOIN raw.teams AS teams
                ON box_scores.team_id = teams.team_id
            WHERE box_scores.game_id = ?
            """,
            [game_id],
        ).fetchdf()
    finally:
        connection.close()

    if box_scores.empty:
        raise ValueError(f"No local player box score is available for game {game_id}")

    return box_scores


def fetch_fallback_rotation_stints(
    game_id: str,
    database_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch play-by-play and reconstruct rotations using local box scores."""

    from rotation_lab.ingest.play_by_play import fetch_play_by_play

    box_scores = fetch_local_box_scores(
        game_id=game_id,
        database_path=database_path,
    )
    play_by_play = fetch_play_by_play(game_id)
    rotation_stints = reconstruct_rotation_stints(
        game_id=game_id,
        play_by_play=play_by_play,
        box_scores=box_scores,
    )

    return rotation_stints, play_by_play


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

        try:
            rotation_stints = fetch_rotation_stints(game_id)
            validate_rotation_minutes(
                rotation_stints=rotation_stints,
                box_scores=fetch_local_box_scores(
                    game_id=game_id,
                    database_path=database_path,
                ),
            )
        except (RotationDataUnavailableError, ValueError):
            from rotation_lab.ingest.play_by_play import load_play_by_play

            rotation_stints, play_by_play = fetch_fallback_rotation_stints(
                game_id=game_id,
                database_path=database_path,
            )
            load_play_by_play(
                game_id=game_id,
                database_path=database_path,
                frame=play_by_play,
            )
    else:
        rotation_stints = frame.copy()

    missing_columns = set(ROTATION_STINT_COLUMNS).difference(rotation_stints.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Rotation stints are missing required columns: {missing}")

    connection = connect_database(database_path)

    try:
        connection.execute("BEGIN TRANSACTION")
        connection.register(
            "rotation_stints_frame",
            rotation_stints,
        )
        connection.execute(
            """
            DELETE FROM raw.rotation_stints
            WHERE game_id IN (
                SELECT DISTINCT CAST(game_id AS VARCHAR)
                FROM rotation_stints_frame
            )
            """
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
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    return len(rotation_stints)
