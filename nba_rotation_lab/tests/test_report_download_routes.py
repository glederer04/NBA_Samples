"""Exercise actual browser-facing PDF responses and selection validation."""

from io import BytesIO

import pytest
from pypdf import PdfReader

import app as application
from pages import game_review, scenario_planner
from rotation_lab.config import DEMO_DATABASE_PATH
from rotation_lab.dashboard import data
from rotation_lab.reporting import downloads


@pytest.fixture(autouse=True)
def demo_data(monkeypatch):
    monkeypatch.setattr(data, "DATABASE_PATH", DEMO_DATABASE_PATH)
    monkeypatch.setattr(downloads, "DATABASE_PATH", DEMO_DATABASE_PATH)


def test_game_attachment_and_inline_preview():
    game = data.get_team_games("NYK")[0]["value"]
    download, preview, _ = game_review.game_report_links("NYK", game)
    client = application.server.test_client()
    for url, disposition in [(download, "attachment"), (preview, "inline")]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.headers["Content-Disposition"].startswith(disposition)
        assert int(response.headers["Content-Length"]) == len(response.data)
        assert len(PdfReader(BytesIO(response.data)).pages) >= 2
    assert client.get("/reports/game/NYK/not-a-game.pdf").status_code == 404
    assert game_review.game_report_links(None, None)[:2] == (None, None)


def test_scenario_attachment_matches_current_plan():
    pool = data.get_planner_recommendations("NYK", limit=3)
    keys = [row.lineup_key for row in pool]
    url, preview, _ = scenario_planner.scenario_report_links("NYK", *keys, 16, 16, 16)
    client = application.server.test_client()
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment")
    reader = PdfReader(BytesIO(response.data))
    assert len(reader.pages) == 2
    assert "48.0" in reader.pages[0].extract_text()
    assert client.get(preview).headers["Content-Disposition"].startswith("inline")
    assert scenario_planner.scenario_report_links("NYK", *keys, 30, 16, 16)[:2] == (None, None)
    query = downloads.scenario_query(keys, [30, 16, 16])
    assert client.get("/reports/scenario/NYK.pdf?" + query).status_code == 400
    for bad in ["nan", "inf", "-1", "text"]:
        query = f"lineup={keys[0]}&minutes={bad}"
        assert client.get("/reports/scenario/NYK.pdf?" + query).status_code == 400


def test_generation_failure_returns_readable_retry_page(monkeypatch):
    def fail(*args):
        raise RuntimeError("not for display")

    monkeypatch.setattr(downloads, "game_pdf", fail)
    response = application.server.test_client().get("/reports/game/NYK/example.pdf")
    assert response.status_code == 503
    assert b"Please retry" in response.data
    assert b"not for display" not in response.data
