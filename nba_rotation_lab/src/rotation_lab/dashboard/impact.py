"""Descriptive player on/off from unchanged scored lineup intervals.

All aggregation uses unrounded seconds. Resampling units are whole games, with
the same draws for ON and OFF (and both players in a matched comparison).
"""

import numpy as np
import pandas as pd

from rotation_lab.config import DATABASE_PATH, SQL_DIR
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.database import connect_database, run_sql_file

MIN_MINUTES = 100
MIN_GAMES = 10
BOOTSTRAP_DRAWS = 2000


def initialize_impact_views():
    """Migrate existing deployment snapshots before Dash opens reader connections."""
    with connect_database(DATABASE_PATH) as connection:
        connection.execute("BEGIN TRANSACTION")
        for name in (
            "03_intermediate/003_create_player_interval_membership.sql",
            "04_marts/010_create_player_on_off.sql",
        ):
            run_sql_file(connection, SQL_DIR / name)
        connection.execute("COMMIT")


@database_cached(lambda: DATABASE_PATH)
def team_dataset(team):
    """Load each scored interval once, with normalized membership and game quality."""
    if team not in {"NYK", "SAS"}:
        raise ValueError("Player Impact supports NYK and SAS.")
    with connect_database(DATABASE_PATH, read_only=True) as connection:
        intervals = connection.execute(
            """
            SELECT * EXCLUDE (player_id), LIST(player_id ORDER BY player_id) AS players
            FROM marts.player_on_off_intervals
            WHERE team_abbreviation = ? GROUP BY ALL
            ORDER BY game_id, interval_number
            """,
            [team],
        ).fetchdf()
        games = connection.execute(
            """
            SELECT g.game_id, g.game_date, g.season_id, g.season_type,
                CASE WHEN g.home_team_abbreviation = ? THEN g.away_team_abbreviation
                    ELSE g.home_team_abbreviation END AS opponent,
                COALESCE(c.valid_duration_seconds, 0) AS valid_seconds,
                COALESCE(p.final_event_deciseconds, 28800) / 10.0 AS expected_seconds,
                COALESCE(c.coverage_status = 'complete' AND p.final_score_matches
                    AND v.score_matches AND ABS(c.valid_duration_seconds
                    - p.final_event_deciseconds / 10.0) < 0.11, FALSE) AS quality_ok
            FROM raw.games g
            LEFT JOIN marts.team_lineup_interval_coverage c
                ON g.game_id = c.game_id AND c.team_abbreviation = ?
            LEFT JOIN marts.play_by_play_coverage p ON g.game_id = p.game_id
            LEFT JOIN marts.lineup_scoring_validation v ON g.game_id = v.game_id
            WHERE g.home_team_abbreviation = ? OR g.away_team_abbreviation = ?
            ORDER BY g.game_date, g.game_id
            """,
            [team] * 4,
        ).fetchdf()
        players = connection.execute(
            """
            SELECT r.player_id, MAX(r.player_name) AS player_name,
                SUM(r.duration_seconds) AS seconds
            FROM raw.rotation_stints r JOIN raw.games g USING (game_id)
            WHERE (g.home_team_abbreviation = ? AND r.team_id = g.home_team_id)
                OR (g.away_team_abbreviation = ? AND r.team_id = g.away_team_id)
            GROUP BY r.player_id ORDER BY seconds DESC, player_name
            """,
            [team, team],
        ).fetchdf()
        appearances = connection.execute(
            """
            SELECT DISTINCT r.game_id, r.player_id
            FROM raw.rotation_stints r JOIN raw.games g USING (game_id)
            WHERE r.duration_seconds > 0 AND (
                (g.home_team_abbreviation = ? AND r.team_id = g.home_team_id)
                OR (g.away_team_abbreviation = ? AND r.team_id = g.away_team_id))
            """,
            [team, team],
        ).fetchdf()
    return dict(intervals=intervals, games=games, players=players, appearances=appearances)


def filter_sample(
    dataset,
    player_ids,
    season=None,
    start=None,
    end=None,
    universe="appearances",
    quality="validated",
    exclude_boundary=False,
    game_id=None,
):
    """Apply one universe and quality mask before computing any player's totals."""
    games = dataset["games"].copy()
    if season and season != "all":
        games = games[games.season_id.astype(str) == str(season)]
    if start:
        games = games[games.game_date >= pd.Timestamp(start)]
    if end:
        games = games[games.game_date <= pd.Timestamp(end)]
    if game_id:
        games = games[games.game_id == game_id]
    if universe == "appearances":
        for player in player_ids:
            appearances = dataset["appearances"]
            games = games[
                games.game_id.isin(appearances.loc[appearances.player_id == player, "game_id"])
            ]
    requested = games.copy()
    if quality == "validated":
        games = games[games.quality_ok]
    intervals = dataset["intervals"]
    intervals = intervals[intervals.game_id.isin(games.game_id)].copy()
    before = float(intervals.duration_seconds.sum())
    if exclude_boundary:
        intervals = intervals[intervals.boundary_scoring_points == 0]
    included = games[games.game_id.isin(intervals.game_id)]
    expected = float(requested.expected_seconds.sum())
    return intervals, {
        "requested_games": len(requested),
        "games": len(included),
        "excluded_games": len(requested) - len(included),
        "flagged_games": int((~included.quality_ok).sum()),
        "covered_minutes": float(intervals.duration_seconds.sum()) / 60,
        "coverage": 100 * float(intervals.duration_seconds.sum()) / expected if expected else 0,
        "boundary_excluded_minutes": (before - float(intervals.duration_seconds.sum())) / 60,
        "boundary_points": int(intervals.boundary_scoring_points.sum()),
        "start": str(included.game_date.min().date()) if len(included) else None,
        "end": str(included.game_date.max().date()) if len(included) else None,
    }


def game_arrays(intervals, player):
    """Columns are seconds, points for, points against; axis 1 is ON then OFF."""
    if intervals.empty:
        return np.zeros((0, 2, 3))
    cols = ["duration_seconds", "points_for", "points_against"]
    total = intervals.groupby("game_id", sort=True)[cols].sum()
    on = intervals[intervals.players.map(lambda ids: player in ids)].groupby("game_id")[cols].sum()
    on = on.reindex(total.index, fill_value=0)
    return np.stack([on.to_numpy(float), (total - on).to_numpy(float)], axis=1)


def rates(totals):
    """Margin, team points, opponent points, all per 48 minutes."""
    seconds = totals[..., 0]
    numerators = np.stack([totals[..., 1] - totals[..., 2], totals[..., 1], totals[..., 2]], -1)
    return np.divide(
        2880 * numerators,
        seconds[..., None],
        out=np.full_like(numerators, np.nan),
        where=seconds[..., None] > 0,
    )


def summarize(intervals, player, bootstrap=True):
    arrays = game_arrays(intervals, player)
    totals = arrays.sum(axis=0)
    values = rates(totals)
    exposure_games = (arrays[..., 0] > 0).sum(axis=0)
    sufficient = (totals[:, 0] >= MIN_MINUTES * 60) & (exposure_games >= MIN_GAMES)
    ci = [None, None, None]
    draws = None
    if bootstrap and len(arrays) >= MIN_GAMES:
        indexes = np.random.default_rng(20260908).integers(
            0, len(arrays), size=(BOOTSTRAP_DRAWS, len(arrays))
        )
        draws = rates(arrays[indexes].sum(axis=1))
        for side in range(2):
            if sufficient[side] and np.isfinite(draws[:, side]).all():
                ci[side] = np.quantile(draws[:, side], [0.025, 0.975], axis=0).tolist()
        if all(sufficient) and all(part is not None for part in ci[:2]):
            ci[2] = np.quantile(draws[:, 0] - draws[:, 1], [0.025, 0.975], axis=0).tolist()
    return dict(
        player=player,
        totals=totals.tolist(),
        rates=values.tolist(),
        swing=(values[0] - values[1]).tolist(),
        games=exposure_games.tolist(),
        sufficient=sufficient.tolist(),
        ci=ci,
        draws=draws,
    )


def comparison_interval(first, second):
    """Paired, whole-game CI for the difference in on/off swings."""
    if first["ci"][2] is None or second["ci"][2] is None:
        return None
    a, b = first["draws"], second["draws"]
    return np.quantile((a[:, 0] - a[:, 1]) - (b[:, 0] - b[:, 1]), [0.025, 0.975], axis=0).tolist()
