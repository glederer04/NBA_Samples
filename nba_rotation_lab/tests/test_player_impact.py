"""Conservation, filtering, uncertainty, and real-snapshot on/off validation."""

import json
import shutil

import numpy as np
import pandas as pd
import pytest
from plotly.utils import PlotlyJSONEncoder

from rotation_lab.config import DEMO_DATABASE_PATH
from rotation_lab.dashboard import impact
from rotation_lab.dashboard.impact_components import comparison_card
from rotation_lab.database import connect_database, initialize_database


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory):
    path = tmp_path_factory.mktemp("impact") / "sample.duckdb"
    shutil.copy2(DEMO_DATABASE_PATH, path)
    initialize_database(path)
    return path


@pytest.mark.parametrize("team", ["NYK", "SAS"])
def test_membership_and_point_conservation(snapshot, monkeypatch, team):
    monkeypatch.setattr(impact, "DATABASE_PATH", snapshot)
    data = impact.team_dataset(team)
    intervals, meta = impact.filter_sample(data, [], universe="all")
    assert len(intervals) > 1000
    assert meta["coverage"] == pytest.approx(100)
    assert all(len(ids) == len(set(ids)) == 5 for ids in intervals.players)
    expected = intervals[["duration_seconds", "points_for", "points_against"]].sum().to_numpy()
    total_player_seconds = 0
    for player in data["players"].player_id:
        arrays = impact.game_arrays(intervals, player)
        np.testing.assert_allclose(arrays.sum(axis=(0, 1)), expected)
        total_player_seconds += arrays[:, 0, 0].sum()
        direct = intervals[intervals.players.map(lambda ids, p=player: p in ids)]
        np.testing.assert_allclose(
            arrays[:, 0].sum(axis=0),
            direct[["duration_seconds", "points_for", "points_against"]].sum(),
        )
    assert total_player_seconds == pytest.approx(5 * expected[0])
    with connect_database(snapshot, read_only=True) as connection:
        assert (
            connection.execute("""
            SELECT COUNT(*) FROM marts.player_on_off_game
            WHERE ABS(on_seconds + off_seconds - covered_seconds) > 0.001
                OR on_points_for + off_points_for != covered_points_for
                OR on_points_against + off_points_against != covered_points_against
        """).fetchone()[0]
            == 0
        )


def synthetic():
    rows = []
    for game in range(12):
        for side in range(2):
            rows.append(
                dict(
                    game_id=str(game),
                    duration_seconds=1440.0,
                    points_for=30 + game * (1 if side else 2),
                    points_against=30,
                    players=[1, 3, 4, 5, 6] if side == 0 else [2, 3, 4, 5, 6],
                    boundary_scoring_points=2 if side else 0,
                )
            )
    intervals = pd.DataFrame(rows)
    games = pd.DataFrame(
        [
            dict(
                game_id=str(g),
                game_date=pd.Timestamp("2025-11-01") + pd.Timedelta(days=g),
                season_id="22025",
                quality_ok=g != 11,
                expected_seconds=2880.0,
            )
            for g in range(12)
        ]
    )
    appearances = pd.DataFrame(
        [dict(game_id=str(g), player_id=p) for g in range(12) for p in ([1, 2] if g != 10 else [2])]
    )
    return dict(intervals=intervals, games=games, appearances=appearances)


def test_universe_quality_dates_and_sensitivity_are_applied_before_subtraction():
    data = synthetic()
    sample, meta = impact.filter_sample(data, [1], start="2025-11-02")
    assert set(sample.game_id) == {str(g) for g in range(1, 10)}
    assert meta["excluded_games"] == 1
    assert meta["coverage"] == pytest.approx(90)
    all_games, _ = impact.filter_sample(data, [1], universe="all", quality="partial")
    assert all_games.game_id.nunique() == 12
    sample, meta = impact.filter_sample(data, [1, 2], quality="partial", exclude_boundary=True)
    assert sample.boundary_scoring_points.sum() == 0
    assert meta["boundary_excluded_minutes"] == pytest.approx(11 * 24)
    arrays = impact.game_arrays(sample, 1)
    assert arrays[:, 1, 0].sum() == 0
    assert np.isnan(impact.summarize(sample, 1)["swing"]).all()
    empty, _ = impact.filter_sample(data, [1], start="2027-01-01")
    assert impact.summarize(empty, 1)["games"] == [0, 0]


def test_whole_game_bootstrap_is_paired_deterministic_and_sample_guarded():
    intervals = synthetic()["intervals"]
    a = impact.summarize(intervals, 1)
    again = impact.summarize(intervals, 1)
    b = impact.summarize(intervals, 2)
    np.testing.assert_array_equal(a["draws"], again["draws"])
    assert all(a["sufficient"])
    # Two players alternate: B's swing is exactly the negative of A's in every draw.
    np.testing.assert_allclose(a["draws"][:, 0], b["draws"][:, 1])
    np.testing.assert_allclose(impact.comparison_interval(a, b), 2 * np.array(a["ci"][2]))
    np.testing.assert_allclose(impact.comparison_interval(a, a), np.zeros((2, 3)))
    assert impact.summarize(intervals[intervals.game_id == "0"], 1)["ci"] == [None] * 3
    # A full-game player has no off sample, even with many on minutes and games.
    full = impact.summarize(intervals, 3)
    assert full["ci"][0] is not None
    assert full["ci"][1:] == [None, None]
    assert np.isnan(full["swing"]).all()


def test_rates_use_total_exposure_not_average_interval_rates():
    intervals = pd.DataFrame(
        [
            dict(game_id="ot", duration_seconds=60.0, points_for=10, points_against=0, players=[1]),
            dict(
                game_id="ot", duration_seconds=3120.0, points_for=20, points_against=10, players=[2]
            ),
        ]
    )
    result = impact.summarize(intervals, 1)
    assert result["rates"][0][0] == 480
    assert result["rates"][1][0] == pytest.approx(48 * 10 / 52)
    assert sum(part[0] for part in result["totals"]) == 53 * 60


def test_matched_comparison_filters_both_appearances(snapshot, monkeypatch):
    monkeypatch.setattr(impact, "DATABASE_PATH", snapshot)
    data = impact.team_dataset("NYK")
    ids = data["players"].player_id.iloc[:2].tolist()
    sample, meta = impact.filter_sample(data, ids)
    appearances = data["appearances"]
    common = set(appearances.loc[appearances.player_id == ids[0], "game_id"]) & set(
        appearances.loc[appearances.player_id == ids[1], "game_id"]
    )
    assert set(sample.game_id) == common
    assert meta["games"] < 82
    assert impact.comparison_interval(*(impact.summarize(sample, p) for p in ids)) is not None


def test_comparison_card_suppresses_edge_badges_for_small_samples():
    intervals = synthetic()["intervals"]
    small = intervals[intervals.game_id == "0"]
    card = comparison_card(impact.summarize(small, 1), impact.summarize(small, 2), ["A", "B"])
    content = json.dumps(card, cls=PlotlyJSONEncoder)
    assert "Not enough exposure" in content
    assert '"className": "impact-edge"' not in content
    full = comparison_card(
        impact.summarize(intervals, 1), impact.summarize(intervals, 2), ["A", "B"]
    )
    content = json.dumps(full, cls=PlotlyJSONEncoder)
    assert '"className": "impact-edge"' in content
    assert "While on court" in content


def test_only_featured_teams_are_selectable(snapshot, monkeypatch):
    from rotation_lab.dashboard import data

    monkeypatch.setattr(data, "DATABASE_PATH", snapshot)
    assert {row["value"] for row in data.get_dashboard_teams()} == {"NYK", "SAS"}
    with pytest.raises(ValueError, match="NYK and SAS"):
        impact.team_dataset("BOS")
