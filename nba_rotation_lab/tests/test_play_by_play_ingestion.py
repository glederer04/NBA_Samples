"""Tests for NBA play-by-play ingestion."""

from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.play_by_play import (
    calculate_game_elapsed_deciseconds,
    load_play_by_play,
    normalize_play_by_play,
    parse_clock_seconds,
)


def sample_play_by_play() -> pd.DataFrame:
    """Return representative play-by-play events."""

    return pd.DataFrame(
        [
            {
                "gameId": "0022500001",
                "actionId": 1,
                "actionNumber": 2,
                "period": 1,
                "clock": "PT12M00.00S",
                "teamId": 0,
                "teamTricode": "",
                "personId": 0,
                "playerName": "",
                "location": "",
                "actionType": "period",
                "subType": "start",
                "description": "Start of 1st Period",
                "shotResult": "",
                "isFieldGoal": 0,
                "shotValue": 0,
                "scoreHome": "0",
                "scoreAway": "0",
                "pointsTotal": 0,
                "videoAvailable": 1,
            },
            {
                "gameId": "0022500001",
                "actionId": 5,
                "actionNumber": 10,
                "period": 1,
                "clock": "PT11M26.00S",
                "teamId": 1610612760,
                "teamTricode": "OKC",
                "personId": 1631096,
                "playerName": "Holmgren",
                "location": "h",
                "actionType": "Made Shot",
                "subType": "Cutting Layup Shot",
                "description": "Holmgren 1' Cutting Layup Shot",
                "shotResult": "Made",
                "isFieldGoal": 1,
                "shotValue": 2,
                "scoreHome": "2",
                "scoreAway": "0",
                "pointsTotal": 2,
                "videoAvailable": 1,
            },
            {
                "gameId": "0022500001",
                "actionId": 150,
                "actionNumber": 300,
                "period": 2,
                "clock": "PT12M00.00S",
                "teamId": 0,
                "teamTricode": "",
                "personId": 0,
                "playerName": "",
                "location": "",
                "actionType": "period",
                "subType": "start",
                "description": "Start of 2nd Period",
                "shotResult": "",
                "isFieldGoal": 0,
                "shotValue": 0,
                "scoreHome": "24",
                "scoreAway": "22",
                "pointsTotal": 46,
                "videoAvailable": 1,
            },
        ]
    )


def test_clock_and_elapsed_time_calculation() -> None:
    """NBA clocks should become game-elapsed timestamps."""

    assert parse_clock_seconds("PT11M26.00S") == 686.0
    assert parse_clock_seconds("PT05M00.00S") == 300.0

    assert (
        calculate_game_elapsed_deciseconds(
            period=1,
            clock_seconds_remaining=720,
        )
        == 0
    )
    assert (
        calculate_game_elapsed_deciseconds(
            period=2,
            clock_seconds_remaining=720,
        )
        == 7200
    )
    assert (
        calculate_game_elapsed_deciseconds(
            period=5,
            clock_seconds_remaining=300,
        )
        == 28800
    )


def test_normalize_play_by_play() -> None:
    """Play-by-play records should become ordered game events."""

    events = normalize_play_by_play(sample_play_by_play())

    assert len(events) == 3
    assert events["game_elapsed_deciseconds"].tolist() == [
        0,
        340,
        7200,
    ]

    opening_event = events.iloc[0]
    made_shot = events.iloc[1]

    assert pd.isna(opening_event["team_id"])
    assert pd.isna(opening_event["player_id"])
    assert bool(opening_event["is_field_goal"]) is False

    assert made_shot["team_abbreviation"] == "OKC"
    assert made_shot["player_id"] == 1631096
    assert made_shot["score_home"] == 2
    assert made_shot["score_away"] == 0
    assert bool(made_shot["is_field_goal"]) is True


def test_load_play_by_play(tmp_path: Path) -> None:
    """Normalized events should load into DuckDB."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    events = normalize_play_by_play(sample_play_by_play())

    row_count = load_play_by_play(
        database_path=database_path,
        frame=events,
    )

    connection = duckdb.connect(
        database=str(database_path),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                action_id,
                period,
                game_elapsed_deciseconds,
                team_abbreviation,
                score_home,
                score_away
            FROM raw.play_by_play_events
            ORDER BY action_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert row_count == 3
    assert rows == [
        (1, 1, 0, "", 0, 0),
        (5, 1, 340, "OKC", 2, 0),
        (150, 2, 7200, "", 24, 22),
    ]


def test_load_play_by_play_replaces_all_existing_events_for_game(
    tmp_path: Path,
) -> None:
    """A corrected game load should remove stale events from its prior version."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)
    original_events = normalize_play_by_play(sample_play_by_play())
    corrected_events = original_events.iloc[[0]].copy()

    load_play_by_play(database_path=database_path, frame=original_events)
    load_play_by_play(database_path=database_path, frame=corrected_events)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        action_ids = connection.execute("SELECT action_id FROM raw.play_by_play_events").fetchall()
    finally:
        connection.close()

    assert action_ids == [(1,)]
