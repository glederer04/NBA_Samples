from __future__ import annotations

from typing import Dict, List, Union

PercentileValue = Union[int, float]
PercentileDict = Dict[str, PercentileValue]


def get_top_skills(percentiles: PercentileDict, n: int = 3) -> List[str]:
    """Return the user's strongest skill areas."""
    return [
        skill
        for skill, _ in sorted(
            percentiles.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:n]
    ]


def get_development_areas(
    percentiles: PercentileDict,
    n: int = 2,
) -> List[str]:
    """Return the user's lowest skill areas."""
    return [
        skill
        for skill, _ in sorted(
            percentiles.items(),
            key=lambda item: item[1],
        )[:n]
    ]


def format_skill_name(skill: str) -> str:
    """Convert a percentile column name into a readable skill label."""
    return (
        skill.replace("_PCTL", "")
        .replace("_", " ")
        .title()
    )


def choose_guard_archetype(percentiles: PercentileDict) -> str:
    """Choose an archetype for guard profiles."""
    scoring = percentiles["SCORING_PCTL"]
    shooting = percentiles["SHOOTING_PCTL"]
    playmaking = percentiles["PLAYMAKING_PCTL"]
    defense = percentiles["DEFENSE_PCTL"]
    creation = percentiles["CREATION_PCTL"]
    rim_pressure = percentiles["RIM_PRESSURE_PCTL"]

    if scoring >= 75 and creation >= 75:
        return "Shot-Creating Guard"

    if playmaking >= 75 and creation >= 65:
        return "Lead Playmaker"

    if shooting >= 75 and defense >= 65:
        return "Two-Way Shooting Guard"

    if shooting >= 75:
        return "Floor-Spacing Guard"

    if rim_pressure >= 75:
        return "Pressure Guard"

    if defense >= 75:
        return "Point-of-Attack Defender"

    return "Combo Guard"


def choose_wing_archetype(percentiles: PercentileDict) -> str:
    """Choose an archetype for wing and forward profiles."""
    scoring = percentiles["SCORING_PCTL"]
    shooting = percentiles["SHOOTING_PCTL"]
    playmaking = percentiles["PLAYMAKING_PCTL"]
    defense = percentiles["DEFENSE_PCTL"]
    creation = percentiles["CREATION_PCTL"]
    rim_pressure = percentiles["RIM_PRESSURE_PCTL"]

    if scoring >= 75 and creation >= 70:
        return "Scoring Wing"

    if shooting >= 75 and defense >= 70:
        return "3-and-D Wing"

    if defense >= 75 and rim_pressure >= 65:
        return "Two-Way Slasher"

    if playmaking >= 70:
        return "Connector Forward"

    if rim_pressure >= 75:
        return "Slashing Wing"

    if shooting >= 75:
        return "Spacing Wing"

    return "Two-Way Wing"


def choose_big_archetype(percentiles: PercentileDict) -> str:
    """Choose an archetype for big profiles."""
    scoring = percentiles["SCORING_PCTL"]
    shooting = percentiles["SHOOTING_PCTL"]
    rebounding = percentiles["REBOUNDING_PCTL"]
    defense = percentiles["DEFENSE_PCTL"]
    efficiency = percentiles["EFFICIENCY_PCTL"]
    rim_pressure = percentiles["RIM_PRESSURE_PCTL"]

    if defense >= 75 and rebounding >= 70:
        return "Defensive Anchor"

    if rim_pressure >= 75 and efficiency >= 70:
        return "Rim-Running Big"

    if rebounding >= 80:
        return "Glass Cleaner"

    if shooting >= 70:
        return "Stretch Big"

    if scoring >= 75:
        return "Interior Scoring Big"

    return "Roll-and-Rebound Big"


def choose_archetype(
    position: str,
    percentiles: PercentileDict,
) -> str:
    """Choose an archetype label based on position and skill profile."""
    if position in {"PG", "SG"}:
        return choose_guard_archetype(percentiles)

    if position in {"SF", "PF"}:
        return choose_wing_archetype(percentiles)

    if position == "C":
        return choose_big_archetype(percentiles)

    return "Balanced Player"


def build_archetype_summary(
    position: str,
    percentiles: PercentileDict,
) -> Dict[str, object]:
    """Create a small archetype summary for the dashboard."""
    top_skills = get_top_skills(percentiles)
    development_areas = get_development_areas(percentiles)

    return {
        "archetype": choose_archetype(position, percentiles),
        "strengths": [format_skill_name(skill) for skill in top_skills],
        "development_areas": [
            format_skill_name(skill) for skill in development_areas
        ],
    }
