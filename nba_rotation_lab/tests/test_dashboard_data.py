"""Tests for dashboard data-access validation."""

import pytest

from rotation_lab.dashboard.data import get_lineup_explorer


def test_lineup_explorer_rejects_negative_minutes() -> None:
    """Minimum lineup minutes cannot be negative."""

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        get_lineup_explorer(
            team_abbreviation="NYK",
            minimum_minutes=-1,
        )
