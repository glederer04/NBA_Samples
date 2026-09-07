"""Regression coverage for UI robustness, read caching, and complete exports."""

from io import BytesIO
from pathlib import Path

from dash import no_update
from pypdf import PdfReader

import app  # noqa: F401
from pages import game_review, overview, rotations, scenario_planner
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.reporting.game_report import generate_game_report_bytes


def test_read_cache_copies_results_and_invalidates_on_database_and_wal(tmp_path: Path) -> None:
    database = tmp_path / "sample.duckdb"
    database.write_text("one")
    calls = []

    @database_cached(lambda: database)
    def read(team: str) -> dict:
        calls.append(team)
        return {"rows": [database.read_text()]}

    first = read("NYK")
    first["rows"].append("caller mutation")
    assert read("NYK") == {"rows": ["one"]}
    assert len(calls) == 1
    database.write_text("updated")
    assert read("NYK") == {"rows": ["updated"]}
    Path(str(database) + ".wal").write_text("committed update")
    read("NYK")
    assert len(calls) == 3


def test_rotation_trace_preserves_every_stint_and_tooltip() -> None:
    stints = [
        (1, "Player A", 1, 0, 120, 120),
        (2, "Player B", 1, 0, 180, 180),
        (1, "Player A", 2, 240, 360, 120),
    ]
    figure = rotations.build_rotation_figure(stints, 2880)
    assert len(figure.data) == 1
    assert list(figure.data[0].x) == [2, 3, 2]
    assert list(figure.data[0].base) == [0, 0, 4]
    assert list(figure.data[0].y) == ["Player A", "Player B", "Player A"]
    assert list(figure.data[0].customdata[-1]) == [2, 4, 6, 2]
    assert "No player stints" in rotations.build_rotation_readout({"stints": []}).children


def test_overview_uses_overtime_labels() -> None:
    table = overview.build_recent_games(
        [("game", "2026-01-01", "BOS", "home", "W", 120, 115, 5, 10, 5, 6)], "NYK"
    )
    cells = table.children[1].children[0].children
    assert cells[6].children == "OT1"
    assert cells[7].children == "OT2"


def test_export_wrappers_report_invalid_selection_and_recover_from_errors(monkeypatch) -> None:
    payload, message = game_review.handle_game_report_download(1, None, None)
    assert payload is no_update
    assert "valid game" in message
    payload, message = scenario_planner.handle_scenario_report_download(
        1, None, None, None, None, None, None, None
    )
    assert payload is no_update
    assert "positive minutes" in message

    def fail(*args):
        raise RuntimeError("test failure")

    monkeypatch.setattr(game_review, "download_game_report", fail)
    payload, message = game_review.handle_game_report_download(1, "NYK", "game")
    assert payload is no_update
    assert "retry" in message


def test_game_pdf_includes_stretches_beyond_seven() -> None:
    data = dict(
        game_id="test",
        game_date="2026-01-01",
        team_abbreviation="NYK",
        opponent="BOS",
        team_location="home",
        result="W",
        points_for=100,
        points_against=90,
        plus_minus=10,
        rotation_intervals=9,
        lineups_used=1,
        lineup_changes=8,
        boundary_scoring_points=0,
        best_period=1,
        best_period_plus_minus=10,
        worst_period=2,
        worst_period_plus_minus=0,
        score_matches=True,
        periods=[(1, 100, 90, 10, 1, 9)],
        lineups=[],
        stretches=[
            (1, i * 600, (i + 1) * 600, 60, f"Unique stretch {i}", 2, 1, 1, 0) for i in range(9)
        ],
    )
    reader = PdfReader(BytesIO(generate_game_report_bytes(data=data)))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Unique stretch 8" in text
    assert any(page.images for page in reader.pages)
