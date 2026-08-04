"""Tests for NBA player rotation-stint ingestion."""

from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.rotation_stints import (
    calculate_period,
    load_rotation_stints,
    normalize_rotation_stints,
)


def sample_away_rotation() -> pd.DataFrame:
    """Return one away-player rotation stint."""

    return pd.DataFrame(
        [
            {
                "GAME_ID": "0022500001",
                "TEAM_ID": 1610612745,
                "TEAM_CITY": "Houston",
                "TEAM_NAME": "Rockets",
                "PERSON_ID": 201142,
                "PLAYER_FIRST": "Kevin",
                "PLAYER_LAST": "Durant",
                "IN_TIME_REAL": 0.0,
                "OUT_TIME_REAL": 7200.0,
                "PLAYER_PTS": 8,
                "PT_DIFF": 3.0,
                "USG_PCT": 0.3,
            }
        ]
    )


def sample_home_rotation() -> pd.DataFrame:
    """Return two home-player rotation stints."""

    return pd.DataFrame(
        [
            {
                "GAME_ID": "0022500001",
                "TEAM_ID": 1610612760,
                "TEAM_CITY": "Oklahoma City",
                "TEAM_NAME": "Thunder",
                "PERSON_ID": 1627936,
                "PLAYER_FIRST": "Alex",
                "PLAYER_LAST": "Caruso",
                "IN_TIME_REAL": 0.0,
                "OUT_TIME_REAL": 3000.0,
                "PLAYER_PTS": 2,
                "PT_DIFF": 1.0,
                "USG_PCT": 0.15,
            },
            {
                "GAME_ID": "0022500001",
                "TEAM_ID": 1610612760,
                "TEAM_CITY": "Oklahoma City",
                "TEAM_NAME": "Thunder",
                "PERSON_ID": 1627936,
                "PLAYER_FIRST": "Alex",
                "PLAYER_LAST": "Caruso",
                "IN_TIME_REAL": 4000.0,
                "OUT_TIME_REAL": 7200.0,
                "PLAYER_PTS": 3,
                "PT_DIFF": -1.0,
                "USG_PCT": 0.2,
            },
        ]
    )


def test_calculate_period_supports_regulation_and_overtime() -> None:
    """Game-elapsed times should map to the correct NBA period."""

    assert calculate_period(0) == 1
    assert calculate_period(7200) == 2
    assert calculate_period(21600) == 4
    assert calculate_period(28800) == 5
    assert calculate_period(31800) == 6


def test_normalize_rotation_stints() -> None:
    """Rotation records should become ordered player stints."""

    stints = normalize_rotation_stints(
        away_team=sample_away_rotation(),
        home_team=sample_home_rotation(),
    )

    assert len(stints) == 3

    durant_stint = stints.loc[stints["player_id"] == 201142].iloc[0]
    caruso_stints = stints.loc[stints["player_id"] == 1627936]

    assert durant_stint["team_location"] == "away"
    assert durant_stint["player_name"] == "Kevin Durant"
    assert durant_stint["duration_seconds"] == 720.0
    assert durant_stint["period"] == 1

    assert caruso_stints["stint_number"].tolist() == [1, 2]
    assert caruso_stints["duration_seconds"].tolist() == [
        300.0,
        320.0,
    ]


def test_normalize_rotation_stints_discards_zero_duration_records() -> None:
    """Zero-duration source artifacts should not become real stints."""

    home_rotation = sample_home_rotation()
    zero_duration_record = home_rotation.iloc[[0]].copy()
    zero_duration_record["PERSON_ID"] = 1642276
    zero_duration_record["PLAYER_FIRST"] = "Test"
    zero_duration_record["PLAYER_LAST"] = "Artifact"
    zero_duration_record["IN_TIME_REAL"] = 28739.0
    zero_duration_record["OUT_TIME_REAL"] = 28739.0

    home_rotation = pd.concat(
        [home_rotation, zero_duration_record],
        ignore_index=True,
    )

    stints = normalize_rotation_stints(
        away_team=sample_away_rotation(),
        home_team=home_rotation,
    )

    assert len(stints) == 3
    assert 1642276 not in stints["player_id"].tolist()


def test_load_rotation_stints(tmp_path: Path) -> None:
    """Normalized rotation stints should load into DuckDB."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    stints = normalize_rotation_stints(
        away_team=sample_away_rotation(),
        home_team=sample_home_rotation(),
    )

    row_count = load_rotation_stints(
        database_path=database_path,
        frame=stints,
    )

    connection = duckdb.connect(
        database=str(database_path),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                player_name,
                stint_number,
                duration_seconds
            FROM raw.rotation_stints
            ORDER BY
                player_name,
                stint_number
            """
        ).fetchall()
    finally:
        connection.close()

    assert row_count == 3
    assert rows == [
        ("Alex Caruso", 1, 300.0),
        ("Alex Caruso", 2, 320.0),
        ("Kevin Durant", 1, 720.0),
    ]
