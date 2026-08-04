"""Tests for NBA game ingestion."""

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.games import load_games, normalize_games


def sample_team_games() -> pd.DataFrame:
    """Return two team-level records for one completed game."""

    return pd.DataFrame(
        [
            {
                "GAME_ID": "0022500001",
                "SEASON_ID": "22025",
                "GAME_DATE": "2025-10-22",
                "TEAM_ID": 1610612752,
                "TEAM_ABBREVIATION": "NYK",
                "MATCHUP": "NYK vs. BOS",
                "PTS": 112,
            },
            {
                "GAME_ID": "0022500001",
                "SEASON_ID": "22025",
                "GAME_DATE": "2025-10-22",
                "TEAM_ID": 1610612738,
                "TEAM_ABBREVIATION": "BOS",
                "MATCHUP": "BOS @ NYK",
                "PTS": 108,
            },
        ]
    )


def test_normalize_games_creates_one_game_record() -> None:
    """Two team records should become one game record."""

    games = normalize_games(
        team_games=sample_team_games(),
        season_type="Regular Season",
    )

    assert len(games) == 1

    game = games.iloc[0]

    assert game["game_id"] == "0022500001"
    assert game["game_date"] == date(2025, 10, 22)
    assert game["home_team_abbreviation"] == "NYK"
    assert game["away_team_abbreviation"] == "BOS"
    assert game["home_score"] == 112
    assert game["away_score"] == 108


def test_normalize_games_handles_duplicate_away_matchup_format() -> None:
    """NBA responses may use the away matchup label on both team rows."""

    team_games = sample_team_games()
    team_games.loc[
        team_games["TEAM_ABBREVIATION"] == "NYK",
        "MATCHUP",
    ] = "BOS @ NYK"

    games = normalize_games(
        team_games=team_games,
        season_type="Regular Season",
    )

    game = games.iloc[0]

    assert game["home_team_abbreviation"] == "NYK"
    assert game["away_team_abbreviation"] == "BOS"
    assert game["home_score"] == 112
    assert game["away_score"] == 108


def test_load_games_inserts_normalized_game(tmp_path: Path) -> None:
    """Game loading should insert the normalized record."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)

    games = normalize_games(
        team_games=sample_team_games(),
        season_type="Regular Season",
    )

    row_count = load_games(
        database_path=database_path,
        frame=games,
    )

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        row = connection.execute(
            """
            SELECT
                game_id,
                home_team_abbreviation,
                away_team_abbreviation,
                home_score,
                away_score
            FROM raw.games
            """
        ).fetchone()
    finally:
        connection.close()

    assert row_count == 1
    assert row == ("0022500001", "NYK", "BOS", 112, 108)
