from __future__ import annotations

from pathlib import Path
from typing import Optional, cast

import pandas as pd

try:
    from .similarity import SIMILARITY_COLUMNS
except ImportError:
    from similarity import SIMILARITY_COLUMNS


REQUIRED_COLUMNS = [
    "PLAYER_NAME",
    "SEASON",
    "TEAM_ABBREVIATION",
    "POSITION",
    "PROFILE_GROUP",
    "AGE",
    "PTS",
    "REB",
    "AST",
    "TS_PCT",
    "USG_PCT",
    "ARCHETYPE",
] + SIMILARITY_COLUMNS


def get_default_data_path() -> Path:
    """Return the default path for the dashboard player profile CSV."""
    return Path(__file__).resolve().parents[1] / "data" / "player_similarity_profiles.csv"


def validate_columns(player_df: pd.DataFrame) -> None:
    """Raise an error if the player profile dataset is missing required columns."""
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(player_df.columns))

    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required data columns: {missing_text}")


def clean_player_profiles(player_df: pd.DataFrame) -> pd.DataFrame:
    """Clean key columns used by the dashboard."""
    clean_df = player_df.copy()

    for column in SIMILARITY_COLUMNS:
        numeric_series = cast(
            pd.Series,
            pd.to_numeric(clean_df[column], errors="coerce"),
        )
        clean_df[column] = numeric_series.fillna(50).clip(0, 100)

    numeric_columns = ["AGE", "PTS", "REB", "AST", "TS_PCT", "USG_PCT"]

    for column in numeric_columns:
        clean_df[column] = pd.to_numeric(clean_df[column], errors="coerce")

    text_columns = [
        "PLAYER_NAME",
        "SEASON",
        "TEAM_ABBREVIATION",
        "POSITION",
        "PROFILE_GROUP",
        "ARCHETYPE",
    ]

    for column in text_columns:
        text_series = cast(pd.Series, clean_df[column])
        clean_df[column] = text_series.fillna("Unknown").astype(str)

    return clean_df


def load_player_profiles(data_path: Optional[Path] = None) -> pd.DataFrame:
    """Load and validate the player profile dataset."""
    csv_path = data_path or get_default_data_path()

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Player profile CSV not found at: {csv_path}. "
            "Export player_similarity_profiles.csv before running the dashboard."
        )

    player_df = pd.read_csv(csv_path)
    validate_columns(player_df)

    return clean_player_profiles(player_df)