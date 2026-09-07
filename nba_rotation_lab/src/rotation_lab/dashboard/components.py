"""Reusable Dash presentation components."""

from dash import html

from rotation_lab.reporting.assets import player_headshot_url


def format_signed(value: int | float) -> str:
    """Format a number with an explicit sign."""

    return f"{value:+g}"


def format_period_label(period: int) -> str:
    """Return a basketball-friendly period label."""

    if period < 1:
        raise ValueError("period must be greater than zero")

    if period <= 4:
        return f"Q{period}"

    return f"OT{period - 4}"


def format_period_clock(
    period: int,
    elapsed_deciseconds: int,
) -> str:
    """Convert game-elapsed deciseconds into a period clock."""

    if period < 1:
        raise ValueError("period must be greater than zero")

    if period <= 4:
        period_start = (period - 1) * 7200
        period_length = 7200
    else:
        period_start = 28800 + (period - 5) * 3000
        period_length = 3000

    elapsed_in_period = elapsed_deciseconds - period_start
    remaining_deciseconds = max(
        period_length - elapsed_in_period,
        0,
    )
    remaining_seconds = round(remaining_deciseconds / 10)
    minutes, seconds = divmod(remaining_seconds, 60)

    return f"{format_period_label(period)} {minutes}:{seconds:02d}"


def build_period_markers(
    game_end_seconds: float,
) -> list[tuple[float, str]]:
    """Return period start times and labels for a game."""

    if game_end_seconds < 0:
        raise ValueError("game_end_seconds cannot be negative")

    markers = [
        (0.0, "Q1"),
        (720.0, "Q2"),
        (1440.0, "Q3"),
        (2160.0, "Q4"),
    ]

    overtime_start = 2880.0
    overtime_number = 1

    while overtime_start < game_end_seconds:
        markers.append(
            (
                overtime_start,
                f"OT{overtime_number}",
            )
        )
        overtime_start += 300.0
        overtime_number += 1

    return markers


def split_lineup(
    lineup_key: str,
    lineup_names: str,
) -> list[tuple[int, str]]:
    """Return ordered player IDs and names from lineup fields."""

    player_ids = [int(player_id) for player_id in lineup_key.split("-")]
    player_names = lineup_names.split(" | ")

    if len(player_ids) != len(player_names):
        raise ValueError("Lineup player IDs and names must have equal lengths")

    return list(
        zip(
            player_ids,
            player_names,
            strict=True,
        )
    )


def metric_card(
    label: str,
    value: str,
    detail: str,
) -> html.Div:
    """Create one executive-summary metric card."""

    return html.Div(
        [
            html.Div(
                label,
                className="metric-label",
            ),
            html.Div(
                value,
                className="metric-value",
            ),
            html.Div(
                detail,
                className="metric-detail",
            ),
        ],
        className="metric-card",
    )


def player_headshot(
    player_id: int,
    player_name: str,
) -> html.Div:
    """Create one compact player headshot."""

    return html.Div(
        [
            html.Div(
                html.Img(
                    src=player_headshot_url(player_id),
                    alt=player_name,
                    title=player_name,
                    className="player-headshot-image",
                ),
                className="player-headshot-frame",
            ),
            html.Div(
                player_name,
                className="player-headshot-name",
            ),
        ],
        className="player-headshot",
    )


def lineup_card(
    lineup_key: str,
    lineup_names: str,
    games_used: int,
    total_minutes: float,
    points_for: int,
    points_against: int,
    plus_minus: int,
    plus_minus_per_48: float,
    sample_size_status: str,
) -> html.Div:
    """Create a five-player lineup performance card."""

    players = split_lineup(
        lineup_key=lineup_key,
        lineup_names=lineup_names,
    )

    plus_minus_class = "positive" if plus_minus > 0 else "negative" if plus_minus < 0 else "neutral"

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                f"{float(total_minutes):.2f} MIN",
                                className="lineup-chip",
                            ),
                            html.Span(
                                f"{games_used} G",
                                className="lineup-chip",
                            ),
                            html.Span(
                                sample_size_status.upper(),
                                className="lineup-chip muted",
                            ),
                        ],
                        className="lineup-chip-row",
                    ),
                    html.Div(
                        [
                            player_headshot(
                                player_id=player_id,
                                player_name=player_name,
                            )
                            for player_id, player_name in players
                        ],
                        className="lineup-headshots",
                    ),
                ],
                className="lineup-card-main",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                "PLUS-MINUS",
                                className="lineup-stat-label",
                            ),
                            html.Strong(
                                format_signed(plus_minus),
                                className=(f"lineup-stat-value {plus_minus_class}"),
                            ),
                        ],
                        className="lineup-stat",
                    ),
                    html.Div(
                        [
                            html.Span(
                                "PLUS-MINUS / 48",
                                className="lineup-stat-label",
                            ),
                            html.Strong(
                                format_signed(float(plus_minus_per_48)),
                                className=(f"lineup-stat-value {plus_minus_class}"),
                            ),
                        ],
                        className="lineup-stat",
                    ),
                    html.Div(
                        [
                            html.Span(
                                "POINTS",
                                className="lineup-stat-label",
                            ),
                            html.Strong(
                                f"{points_for}-{points_against}",
                                className="lineup-stat-value",
                            ),
                        ],
                        className="lineup-stat",
                    ),
                ],
                className="lineup-card-stats",
            ),
        ],
        className="lineup-card",
    )


def team_logo(team_abbreviation: str) -> html.Img:
    """Use bundled NBA logos; keep a readable abbreviation alongside them."""

    from rotation_lab.config import ASSETS_DIR

    abbreviation = team_abbreviation.strip().upper()
    filename = f"{abbreviation}.svg"
    exists = (ASSETS_DIR / "team-logos" / filename).is_file()
    return html.Img(
        src=f"/assets/team-logos/{filename}" if exists else "/assets/team-placeholder.svg",
        alt=f"{abbreviation} logo",
        className="team-logo",
    )


def get_team_options() -> list[dict]:
    """Add team branding in the presentation layer without changing data results."""

    from rotation_lab.dashboard.data import get_dashboard_teams

    return [
        {
            "value": option["value"],
            "search": option["value"],
            "label": html.Span(
                [team_logo(option["value"]), html.Span(option["label"])],
                className="team-option",
            ),
        }
        for option in get_dashboard_teams()
    ]
