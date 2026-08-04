"""Tests for NBA player box-score ingestion."""

from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.box_scores import (
    load_player_box_scores,
    normalize_player_box_scores,
)


def sample_player_box_scores() -> pd.DataFrame:
    """Return two representative NBA player box-score records."""

    return pd.DataFrame(
        [
            {
                "gameId": "0022500001",
                "teamId": 1610612760,
                "teamTricode": "OKC",
                "personId": 1629652,
                "firstName": "Luguentz",
                "familyName": "Dort",
                "position": "F",
                "comment": "",
                "minutes": "35:30",
                "fieldGoalsMade": 5,
                "fieldGoalsAttempted": 10,
                "fieldGoalsPercentage": 0.5,
                "threePointersMade": 2,
                "threePointersAttempted": 5,
                "threePointersPercentage": 0.4,
                "freeThrowsMade": 2,
                "freeThrowsAttempted": 2,
                "freeThrowsPercentage": 1.0,
                "reboundsOffensive": 1,
                "reboundsDefensive": 4,
                "reboundsTotal": 5,
                "assists": 3,
                "steals": 1,
                "blocks": 0,
                "turnovers": 1,
                "foulsPersonal": 2,
                "points": 14,
                "plusMinusPoints": 8.0,
            },
            {
                "gameId": "0022500001",
                "teamId": 1610612760,
                "teamTricode": "OKC",
                "personId": 1631114,
                "firstName": "Jalen",
                "familyName": "Williams",
                "position": "",
                "comment": "",
                "minutes": "12:00",
                "fieldGoalsMade": 2,
                "fieldGoalsAttempted": 4,
                "fieldGoalsPercentage": 0.5,
                "threePointersMade": 1,
                "threePointersAttempted": 2,
                "threePointersPercentage": 0.5,
                "freeThrowsMade": 0,
                "freeThrowsAttempted": 0,
                "freeThrowsPercentage": 0.0,
                "reboundsOffensive": 0,
                "reboundsDefensive": 2,
                "reboundsTotal": 2,
                "assists": 1,
                "steals": 0,
                "blocks": 0,
                "turnovers": 0,
                "foulsPersonal": 1,
                "points": 5,
                "plusMinusPoints": 2.0,
            },
        ]
    )


def test_normalize_player_box_scores() -> None:
    """Box-score normalization should derive lineup-friendly fields."""

    box_scores = normalize_player_box_scores(sample_player_box_scores())

    assert len(box_scores) == 2

    starter = box_scores.loc[box_scores["player_id"] == 1629652].iloc[0]
    reserve = box_scores.loc[box_scores["player_id"] == 1631114].iloc[0]

    assert starter["player_name"] == "Luguentz Dort"
    assert starter["minutes"] == 35.5
    assert bool(starter["starter"]) is True
    assert bool(starter["did_not_play"]) is False

    assert reserve["minutes"] == 12.0
    assert bool(reserve["starter"]) is False


def test_load_player_box_scores(tmp_path: Path) -> None:
    """Normalized player box scores should load into DuckDB."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(
        database_path=database_path,
        sql_directory=SQL_DIR,
    )

    box_scores = normalize_player_box_scores(sample_player_box_scores())

    row_count = load_player_box_scores(
        database_path=database_path,
        frame=box_scores,
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
                minutes,
                starter,
                points
            FROM raw.player_box_scores
            ORDER BY player_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert row_count == 2
    assert rows == [
        ("Luguentz Dort", 35.5, True, 14),
        ("Jalen Williams", 12.0, False, 5),
    ]
