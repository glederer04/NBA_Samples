"""Reusable reporting and dashboard asset URLs."""

NBA_HEADSHOT_TEMPLATE = "https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"


def player_headshot_url(player_id: int) -> str:
    """Return the NBA CDN headshot URL for one player."""

    if player_id < 1:
        raise ValueError("player_id must be greater than zero")

    return NBA_HEADSHOT_TEMPLATE.format(
        player_id=player_id,
    )
