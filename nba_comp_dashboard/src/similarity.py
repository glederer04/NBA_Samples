from __future__ import annotations

from typing import Dict, Union, cast

import numpy as np
import pandas as pd

PercentileValue = Union[int, float]
PercentileDict = Dict[str, PercentileValue]


SIMILARITY_COLUMNS = [
    "SCORING_PCTL",
    "SHOOTING_PCTL",
    "PLAYMAKING_PCTL",
    "REBOUNDING_PCTL",
    "DEFENSE_PCTL",
    "EFFICIENCY_PCTL",
    "RIM_PRESSURE_PCTL",
    "CREATION_PCTL",
]


DISPLAY_COLUMNS = [
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
]


POSITION_TO_PROFILE_GROUP = {
    "PG": "Guard/Wing",
    "SG": "Guard/Wing",
    "SF": "Guard/Wing",
    "PF": "Big",
    "C": "Big",
}


def build_user_vector(percentiles: PercentileDict) -> np.ndarray:
    """Convert user percentile inputs into a numeric vector."""
    return np.array(
        [float(percentiles[column]) for column in SIMILARITY_COLUMNS],
        dtype=float,
    )


def filter_by_position(player_df: pd.DataFrame, position: str) -> pd.DataFrame:
    """Filter player seasons to a broad profile group based on selected position."""
    profile_group = POSITION_TO_PROFILE_GROUP.get(position)

    if profile_group is None or "PROFILE_GROUP" not in player_df.columns:
        return player_df.copy()

    profile_mask = player_df["PROFILE_GROUP"].eq(profile_group)
    filtered_df = player_df.loc[profile_mask, :].copy()

    if filtered_df.empty:
        return player_df.copy()

    return cast(pd.DataFrame, filtered_df)


def add_similarity_scores(
    player_df: pd.DataFrame,
    user_vector: np.ndarray,
) -> pd.DataFrame:
    """Add distance and similarity score columns to a player-season dataframe."""
    comp_df = player_df.copy()

    player_vectors = (
        comp_df[SIMILARITY_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(50)
        .to_numpy(dtype=float)
    )

    distances = np.linalg.norm(player_vectors - user_vector, axis=1)

    comp_df["DISTANCE"] = distances

    max_distance = float(np.nanmax(distances)) if len(distances) else 0

    if max_distance == 0:
        comp_df["SIMILARITY_SCORE"] = 100
    else:
        comp_df["SIMILARITY_SCORE"] = 100 - ((comp_df["DISTANCE"] / max_distance) * 35)

    comp_df["SIMILARITY_SCORE"] = comp_df["SIMILARITY_SCORE"].clip(0, 100)

    return comp_df


def find_similar_players(
    player_df: pd.DataFrame,
    position: str,
    percentiles: PercentileDict,
    top_n: int = 8,
) -> pd.DataFrame:
    """Find the closest NBA player-season comps for a user-created profile."""
    required_columns = set(SIMILARITY_COLUMNS)
    missing_columns = required_columns - set(player_df.columns)

    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required similarity columns: {missing_text}")

    user_vector = build_user_vector(percentiles)
    filtered_df = filter_by_position(player_df, position)
    scored_df = add_similarity_scores(filtered_df, user_vector)

    output_columns = [
        column for column in DISPLAY_COLUMNS if column in scored_df.columns
    ] + [
        column for column in SIMILARITY_COLUMNS if column in scored_df.columns
    ] + [
        "DISTANCE",
        "SIMILARITY_SCORE",
    ]

    result_df = (
        scored_df.sort_values(["DISTANCE", "PLAYER_NAME"], ascending=[True, True])
        .head(top_n)
        .loc[:, output_columns]
        .reset_index(drop=True)
    )

    return cast(pd.DataFrame, result_df)
