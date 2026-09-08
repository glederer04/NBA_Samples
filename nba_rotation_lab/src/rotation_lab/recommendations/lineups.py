"""Coach-facing lineup recommendations."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database

RecommendationLabel = Literal[
    "prioritize",
    "monitor",
    "limit",
    "exploratory",
]


@dataclass(frozen=True, slots=True)
class LineupRecommendation:
    """One sample-adjusted lineup recommendation."""

    team_abbreviation: str
    recommendation_rank: int
    lineup_key: str
    player_names: tuple[str, ...]
    games_used: int
    total_minutes: float
    raw_plus_minus_per_48: float
    adjusted_plus_minus_per_48: float
    team_plus_minus_per_48: float
    confidence_percentage: float
    recommendation: RecommendationLabel
    sample_size_status: str
    latest_game_date: date

    @property
    def baseline_difference(self) -> float:
        """Return adjusted performance relative to team baseline."""

        return round(
            self.adjusted_plus_minus_per_48 - self.team_plus_minus_per_48,
            2,
        )


def get_lineup_recommendations(
    team_abbreviation: str,
    *,
    limit: int = 5,
    database_path: Path = DATABASE_PATH,
    minimum_minutes: float = 0,
    minimum_games: int = 0,
) -> list[LineupRecommendation]:
    """Return the highest-ranked recommendations for one team."""

    normalized_team = team_abbreviation.strip().upper()

    if not normalized_team:
        raise ValueError("team_abbreviation cannot be empty")

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    connection = connect_database(
        database_path,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                recommendation_rank,
                lineup_key,
                lineup_names,
                games_used,
                total_minutes,
                plus_minus_per_48,
                adjusted_plus_minus_per_48,
                team_plus_minus_per_48,
                confidence_percentage,
                recommendation,
                sample_size_status,
                latest_game_date
            FROM marts.lineup_recommendation_pool
            WHERE team_abbreviation = ?
                AND total_minutes >= ?
                AND games_used >= ?
            ORDER BY recommendation_rank
            LIMIT ?
            """,
            [
                normalized_team,
                minimum_minutes,
                minimum_games,
                limit,
            ],
        ).fetchall()
    finally:
        connection.close()

    return [
        LineupRecommendation(
            team_abbreviation=normalized_team,
            recommendation_rank=int(row[0]),
            lineup_key=str(row[1]),
            player_names=tuple(str(row[2]).split(" | ")),
            games_used=int(row[3]),
            total_minutes=float(row[4]),
            raw_plus_minus_per_48=float(row[5]),
            adjusted_plus_minus_per_48=float(row[6]),
            team_plus_minus_per_48=float(row[7]),
            confidence_percentage=float(row[8]),
            recommendation=cast(
                RecommendationLabel,
                str(row[9]),
            ),
            sample_size_status=str(row[10]),
            latest_game_date=row[11],
        )
        for row in rows
    ]


def describe_lineup_recommendation(
    recommendation: LineupRecommendation,
) -> str:
    """Turn a recommendation into a coach-facing explanation."""

    actions: dict[RecommendationLabel, str] = {
        "prioritize": ("Prioritize this unit for additional planned minutes."),
        "monitor": ("Keep this unit in the regular evaluation group."),
        "limit": ("Use this unit selectively while reviewing its fit."),
        "exploratory": ("Treat this unit as exploratory until the sample grows."),
    }

    difference = recommendation.baseline_difference

    if difference > 0:
        comparison = f"{abs(difference):.1f} points per 48 above the team baseline"
    elif difference < 0:
        comparison = f"{abs(difference):.1f} points per 48 below the team baseline"
    else:
        comparison = "in line with the team baseline"

    return (
        f"{actions[recommendation.recommendation]} "
        f"The sample-adjusted margin is {comparison}. "
        f"The unit has played {recommendation.total_minutes:.1f} "
        f"minutes across {recommendation.games_used} games, "
        f"with a {recommendation.confidence_percentage:.1f}% "
        "confidence score. Treat this as decision support, "
        "not a causal estimate."
    )
