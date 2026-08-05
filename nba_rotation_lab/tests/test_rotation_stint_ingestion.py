"""Tests for NBA player rotation-stint ingestion."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from rotation_lab.config import SQL_DIR
from rotation_lab.database import initialize_database
from rotation_lab.ingest.rotation_stints import (
    RotationDataUnavailableError,
    calculate_period,
    fetch_rotation_stints,
    load_rotation_stints,
    match_incoming_player,
    normalize_rotation_stints,
    reconstruct_rotation_stints,
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


def test_fetch_rotation_stints_reports_empty_nba_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty NBA response should become an actionable availability error."""

    class EmptyResponse:
        def get_response(self) -> str:
            return ""

        def valid_json(self) -> bool:
            return False

    def fake_send_api_request(*args, **kwargs):
        return EmptyResponse()

    monkeypatch.setattr(
        "rotation_lab.ingest.rotation_stints.NBAStatsHTTP.send_api_request",
        fake_send_api_request,
    )

    with pytest.raises(
        RotationDataUnavailableError,
        match="empty rotation response",
    ):
        fetch_rotation_stints("0022500082")


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


@pytest.mark.parametrize(
    ("incoming_label", "expected_player_id"),
    [
        ("Se. Curry", 1),
        ("St. Curry", 2),
        ("Hansen", 3),
    ],
)
def test_match_incoming_player_supports_nba_name_variants(
    incoming_label: str,
    expected_player_id: int,
) -> None:
    """NBA substitution abbreviations and reordered names should resolve safely."""

    team_players = pd.DataFrame(
        [
            {"player_id": 1, "player_name": "Seth Curry", "did_not_play": False},
            {"player_id": 2, "player_name": "Stephen Curry", "did_not_play": False},
            {"player_id": 3, "player_name": "Hansen Yang", "did_not_play": False},
        ]
    )

    player = match_incoming_player(
        team_players=team_players,
        incoming_label=incoming_label,
        active_player_ids=set(),
    )

    assert int(player["player_id"]) == expected_player_id


def test_reconstruct_rotation_stints_from_substitutions() -> None:
    """The fallback should preserve five-player coverage for each team."""

    box_score_rows = []

    for team_id, location in [(10, "away"), (20, "home")]:
        for player_number in range(1, 7):
            box_score_rows.append(
                {
                    "team_id": team_id,
                    "player_id": team_id * 100 + player_number,
                    "player_name": (
                        f"Team {team_id} Bench"
                        if player_number == 6
                        else f"Team {team_id} Player {player_number}"
                    ),
                    "starter": player_number <= 5,
                    "did_not_play": False,
                    "minutes": (
                        46.0 if player_number == 1 else 2.0 if player_number == 6 else 48.0
                    ),
                    "team_location": location,
                    "team_city": f"City {team_id}",
                    "team_name": f"Team {team_id}",
                }
            )

    play_by_play = pd.DataFrame(
        [
            {
                "action_number": 1,
                "action_type": "substitution",
                "description": "SUB: Bench FOR Player 1",
                "game_elapsed_deciseconds": 6000,
                "period": 1,
                "player_id": 1001,
                "team_id": 10,
            },
            {
                "action_number": 2,
                "action_type": "substitution",
                "description": "SUB: Bench FOR Player 1",
                "game_elapsed_deciseconds": 6000,
                "period": 1,
                "player_id": 2001,
                "team_id": 20,
            },
            {
                "action_number": 3,
                "action_type": "period",
                "description": "Period End",
                "game_elapsed_deciseconds": 28800,
                "period": 4,
                "player_id": None,
                "team_id": None,
            },
        ]
    )

    stints = reconstruct_rotation_stints(
        game_id="0022500001",
        play_by_play=play_by_play,
        box_scores=pd.DataFrame(box_score_rows),
    )

    team_seconds = stints.groupby("team_id")["duration_seconds"].sum().to_dict()

    assert team_seconds == {10: 14400.0, 20: 14400.0}
    assert stints.loc[stints["player_id"] == 1001, "duration_seconds"].sum() == 2760.0
    assert stints.loc[stints["player_id"] == 1006, "duration_seconds"].sum() == 120.0
    assert (
        stints.loc[
            (stints["player_id"] == 1001) & (stints["period"] == 1),
            "duration_seconds",
        ].sum()
        == 600.0
    )
    assert (
        stints.loc[
            (stints["player_id"] == 1006) & (stints["period"] == 1),
            "duration_seconds",
        ].sum()
        == 120.0
    )


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


def test_load_rotation_stints_replaces_all_existing_rows_for_game(
    tmp_path: Path,
) -> None:
    """A corrected game load should remove stale stints from its prior version."""

    database_path = tmp_path / "test_rotation_lab.duckdb"
    initialize_database(database_path=database_path, sql_directory=SQL_DIR)
    original_stints = normalize_rotation_stints(
        away_team=sample_away_rotation(),
        home_team=sample_home_rotation(),
    )
    corrected_stints = original_stints.loc[original_stints["player_id"].eq(201142)].copy()

    load_rotation_stints(database_path=database_path, frame=original_stints)
    load_rotation_stints(database_path=database_path, frame=corrected_stints)

    connection = duckdb.connect(database=str(database_path), read_only=True)

    try:
        rows = connection.execute("SELECT player_name FROM raw.rotation_stints").fetchall()
    finally:
        connection.close()

    assert rows == [("Kevin Durant",)]
