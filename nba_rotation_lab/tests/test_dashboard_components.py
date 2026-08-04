"""Tests for dashboard presentation helpers."""

import pytest

from rotation_lab.dashboard.components import (
    build_period_markers,
    format_period_clock,
    format_period_label,
    format_signed,
    split_lineup,
)
from rotation_lab.reporting.assets import player_headshot_url


def test_split_lineup_pairs_player_ids_and_names() -> None:
    """Lineup keys should pair with their player names."""

    players = split_lineup(
        lineup_key="1-2-3-4-5",
        lineup_names="A | B | C | D | E",
    )

    assert players == [
        (1, "A"),
        (2, "B"),
        (3, "C"),
        (4, "D"),
        (5, "E"),
    ]


def test_format_signed_displays_direction() -> None:
    """Positive and negative values should be explicit."""

    assert format_signed(8) == "+8"
    assert format_signed(-3) == "-3"
    assert format_signed(0) == "+0"
    assert format_signed(4.5) == "+4.5"


def test_player_headshot_url_uses_player_id() -> None:
    """Player IDs should produce NBA CDN image URLs."""

    assert player_headshot_url(1628973) == (
        "https://cdn.nba.com/headshots/nba/latest/260x190/1628973.png"
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        player_headshot_url(0)


def test_format_period_label_supports_overtime() -> None:
    """Periods should receive basketball-friendly labels."""

    assert format_period_label(1) == "Q1"
    assert format_period_label(4) == "Q4"
    assert format_period_label(5) == "OT1"
    assert format_period_label(6) == "OT2"


def test_format_period_clock_uses_game_elapsed_time() -> None:
    """Game-elapsed time should become a period clock."""

    assert format_period_clock(1, 0) == "Q1 12:00"
    assert format_period_clock(1, 2730) == "Q1 7:27"
    assert format_period_clock(2, 7200) == "Q2 12:00"
    assert format_period_clock(5, 28800) == "OT1 5:00"


def test_build_period_markers_supports_overtime() -> None:
    """Timeline markers should include required overtime periods."""

    assert build_period_markers(2880) == [
        (0.0, "Q1"),
        (720.0, "Q2"),
        (1440.0, "Q3"),
        (2160.0, "Q4"),
    ]

    assert build_period_markers(3480) == [
        (0.0, "Q1"),
        (720.0, "Q2"),
        (1440.0, "Q3"),
        (2160.0, "Q4"),
        (2880.0, "OT1"),
        (3180.0, "OT2"),
    ]
