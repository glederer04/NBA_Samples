"""Regression checks for deployed assets, shared selections, and sample evidence."""

from pathlib import Path

import pytest

import app  # noqa: F401
from pages.rotations import build_rotation_figure
from rotation_lab import config
from rotation_lab.dashboard import data
from rotation_lab.dashboard.data import (
    get_evidence_recommendations,
    get_rotation_timeline,
    get_team_games,
)
from rotation_lab.dashboard.game_selection import resolve_selection


@pytest.fixture(autouse=True)
def demo_database(monkeypatch):
    monkeypatch.setattr(data, "DATABASE_PATH", config.DEMO_DATABASE_PATH)


def test_wheel_install_uses_application_assets(tmp_path, monkeypatch):
    installed = tmp_path / "venv/lib/python/site-packages/rotation_lab/config.py"
    project = tmp_path / "application"
    project.mkdir()
    (project / "app.py").touch()
    (project / "assets").mkdir()
    monkeypatch.setattr(config, "__file__", str(installed))
    monkeypatch.delenv("ROTATION_LAB_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(project)
    assert config.resolve_project_root() == project


def test_shared_game_restores_and_explicit_link_wins():
    games = get_team_games("NYK")
    older = games[1]["value"]
    latest = games[0]["value"]
    saved = {"team": "NYK", "game": older}
    assert resolve_selection("NYK", latest, saved, None, None)[2] == older
    linked = {"team": "NYK", "game": latest}
    assert resolve_selection("NYK", older, saved, linked, None)[2] == latest
    assert resolve_selection("NYK", latest, saved, None, "game-selector")[2] == latest
    selected, team, game, options = resolve_selection(
        "SAS", "invalid", saved, None, "game-team-selector"
    )
    assert team == "SAS"
    assert game == options[0]["value"]
    assert selected == {"team": team, "game": game}


def test_evidence_floor_filters_before_limit_for_both_teams():
    for team in ("NYK", "SAS"):
        rows = get_evidence_recommendations(team)
        assert rows
        assert all(row.total_minutes >= 100 and row.games_used >= 10 for row in rows)
        assert [row.recommendation_rank for row in rows] == list(range(1, len(rows) + 1))
    assert any(row.total_minutes > 500 for row in get_evidence_recommendations("NYK"))


def test_stint_colors_use_margins_and_show_exact_values():
    figure = build_rotation_figure(
        [
            (1, "A", 1, 0, 120, 120, -4),
            (2, "B", 1, 0, 120, 120, 0),
            (1, "A", 2, 240, 360, 120, 6),
        ],
        2880,
    )
    trace = figure.data[0]
    assert list(trace.marker.color) == [-4, 0, 6]
    assert trace.marker.cmin == -trace.marker.cmax
    assert trace.customdata[2][-1] == 6


def test_stint_scoring_reconciles_to_team_score():
    for team in ("NYK", "SAS"):
        game = get_team_games(team)[0]["value"]
        timeline = get_rotation_timeline(team, game)
        assert sum(stint[6] for stint in timeline["stints"]) == 5 * timeline["plus_minus"]


def test_asset_routes_return_images():
    client = app.server.test_client()
    for name in ("NYK", "SAS", "NOP"):
        response = client.get(f"/assets/team-logos/normalized/{name}.png")
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert response.data.startswith(b"\x89PNG")
    assert Path(config.ASSETS_DIR).is_dir()
