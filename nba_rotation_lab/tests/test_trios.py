"""Real-snapshot conservation, completion, filtering and holdout checks."""

import shutil

import numpy as np
import pytest
from pandas.testing import assert_frame_equal

from rotation_lab.config import DEMO_DATABASE_PATH
from rotation_lab.dashboard import game_context, impact, trios
from rotation_lab.database import connect_database, initialize_database
from rotation_lab.lineups.trios import refresh_trios


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory):
    path = tmp_path_factory.mktemp("trios") / "sample.duckdb"
    shutil.copy2(DEMO_DATABASE_PATH, path)
    initialize_database(path)
    refresh_trios(path)
    return path


@pytest.fixture
def wired(snapshot, monkeypatch):
    for module in (impact, trios, game_context):
        monkeypatch.setattr(module, "DATABASE_PATH", snapshot)
    return snapshot


def test_membership_and_refresh_are_exact(wired):
    def totals():
        with connect_database(wired, read_only=True) as db:
            counts = db.execute("""SELECT COUNT(*) FROM (
                SELECT game_id, team_id, interval_number, COUNT(*) n
                FROM intermediate.trio_interval_membership GROUP BY ALL HAVING n != 10
            )""").fetchone()[0]
            assert counts == 0
            return db.execute("SELECT * FROM marts.trio_game_performance ORDER BY ALL").fetchdf()

    before = totals()
    refresh_trios(wired)
    assert_frame_equal(before, totals(), rtol=1e-12, atol=1e-9)
    assert set(before.team_abbreviation) == {"NYK", "SAS"}


@pytest.mark.parametrize("team", ["NYK", "SAS"])
def test_conservation_completions_and_filters(wired, team):
    analysis = trios.trio_analysis(team)
    summary, intervals = analysis["summary"], analysis["intervals"]
    np.testing.assert_allclose(
        summary[["seconds", "points_for", "points_against"]].sum(),
        10 * intervals[["duration_seconds", "points_for", "points_against"]].sum(),
    )
    for key in summary.head(6).index:
        detail = trios.trio_detail(analysis, key)
        sample, completions = detail["sample"], detail["completions"]
        expected = summary.loc[key, ["seconds", "points_for", "points_against"]].astype(float)
        np.testing.assert_allclose(
            sample[["duration_seconds", "points_for", "points_against"]].sum(), expected
        )
        np.testing.assert_allclose(
            completions[["seconds", "points_for", "points_against"]].sum(), expected
        )
        assert completions.share.sum() == pytest.approx(100)
        assert detail["ci"] == trios.trio_detail(analysis, key)["ci"]
        assert list(map(int, key.split("-"))) == sorted(map(int, key.split("-")))
    player = summary.index[0].split("-")[0]
    assert all(player in key.split("-") for key in trios.filter_trios(summary, [player]).index)
    assert all(
        player not in key.split("-") for key in trios.filter_trios(summary, excluded=[player]).index
    )
    assert trios.filter_trios(summary, [player], [player]).empty
    assert trios.filter_trios(summary, [1, 2, 3, 4]).empty
    empty = trios.trio_analysis(team, "2099-01-01", "2099-02-01")
    assert empty["summary"].empty
    assert not empty["model"]["available"]


@pytest.mark.parametrize("team", ["NYK", "SAS"])
def test_untouched_test_games_do_not_choose_weight(wired, team):
    data = trios.trio_analysis(team)
    original = data["model"]
    assert original["available"]
    games = data["games"].copy()
    future = games.game_date.astype(str) > original["validation_end"]
    games.loc[future, "points_for"] += 100
    changed = trios.calibration(games, data["intervals"])
    assert changed["strength"] == original["strength"]
    assert changed["validation_error"] == original["validation_error"]
    assert changed["adjusted_error"] != original["adjusted_error"]


@pytest.mark.parametrize("team", ["NYK", "SAS"])
def test_game_context_matches_source(wired, team):
    data = trios.trio_analysis(team)
    game = data["games"].game_id.iloc[-1]
    context = game_context.game_context(team, game)
    assert len(context["trios"]) == 3
    intervals = data["intervals"][data["intervals"].game_id == game]
    for player in context["players"]:
        direct = impact.summarize(intervals, player["player"], bootstrap=False)
        assert player["swing"] == pytest.approx(direct["swing"][0], nan_ok=True)
    for core in context["trios"]:
        ids = set(map(int, core["key"].split("-")))
        sample = intervals[
            intervals.players.map(lambda values, members=ids: members.issubset(values))
        ]
        assert core["minutes"] == pytest.approx(sample.duration_seconds.sum() / 60)
        assert core["points_for"] == sample.points_for.sum()


@pytest.mark.parametrize("team", ["NYK", "SAS"])
def test_pdf_export_contains_shared_player_and_core_values(wired, monkeypatch, team):
    from io import BytesIO

    from pypdf import PdfReader

    from rotation_lab.dashboard import data
    from rotation_lab.reporting import downloads

    monkeypatch.setattr(data, "DATABASE_PATH", wired)
    monkeypatch.setattr(downloads, "DATABASE_PATH", wired)
    analysis = trios.trio_analysis(team)
    game = analysis["games"].game_id.iloc[-1]
    context = game_context.game_context(team, game)
    content, filename = downloads.game_pdf(team, game)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    assert filename.endswith(".pdf")
    assert "Player on/off" in text
    assert "Three most-used cores" in text
    assert context["players"][0]["name"] in text
    assert f"{context['trios'][0]['minutes']:.1f}" in text
    assert "SWING / 48" in text
    assert "not player quality" in text
