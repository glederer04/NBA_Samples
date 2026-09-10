"""Tests for the Game Review PDF download callback."""

from base64 import b64decode
from typing import Any

import pytest
from dash import no_update

import app  # noqa: F401  # Import initializes the Dash page registry.
from pages import game_review


def test_download_game_report_returns_pdf_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid game selection should return a downloadable PDF."""

    report_data = {
        "game_id": "0022500153",
        "team_abbreviation": "NYK",
    }

    def fake_get_game_review(
        team_abbreviation: str,
        game_id: str,
    ) -> dict[str, Any]:
        assert team_abbreviation == "nyk"
        assert game_id == "0022500153"
        return report_data

    def fake_generate_game_report_bytes(
        *,
        data: dict[str, Any],
    ) -> bytes:
        assert data == {**report_data, "player_context": {"players": [], "trios": []}}
        return b"%PDF-1.7\nmock report"

    monkeypatch.setattr(
        game_review,
        "get_game_review",
        fake_get_game_review,
    )
    monkeypatch.setattr(
        game_review,
        "generate_game_report_bytes",
        fake_generate_game_report_bytes,
    )
    monkeypatch.setattr(
        game_review,
        "enrich_game_report",
        lambda data: {**data, "player_context": {"players": [], "trios": []}},
    )

    result = game_review.download_game_report(
        n_clicks=1,
        team_abbreviation="nyk",
        game_id="0022500153",
    )

    assert isinstance(result, dict)
    assert result["filename"] == "NYK_0022500153_game_report.pdf"
    assert result["type"] == "application/pdf"
    assert result["base64"] is True
    assert b64decode(result["content"]).startswith(b"%PDF")


def test_download_game_report_ignores_incomplete_selection() -> None:
    """No download should occur without a complete selection."""

    result = game_review.download_game_report(
        n_clicks=None,
        team_abbreviation="NYK",
        game_id="0022500153",
    )

    assert result is no_update
