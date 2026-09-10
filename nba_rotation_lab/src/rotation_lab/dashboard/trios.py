"""Sample-aware trio summaries and chronological shrinkage validation."""

import numpy as np

from rotation_lab.config import DATABASE_PATH
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.dashboard.impact import filter_sample, team_dataset
from rotation_lab.database import connect_database

CANDIDATES = (0, 24, 48, 100, 200, 400, 800)


@database_cached(lambda: DATABASE_PATH)
def trio_games(team):
    if team not in {"NYK", "SAS"}:
        raise ValueError("Trio analysis supports NYK and SAS.")
    with connect_database(DATABASE_PATH, read_only=True) as connection:
        return connection.execute(
            """
            SELECT * FROM marts.trio_game_performance WHERE team_abbreviation = ?
            ORDER BY game_date, game_id, trio_key
        """,
            [team],
        ).fetchdf()


def aggregate(games):
    columns = ["seconds", "points_for", "points_against", "boundary_points", "intervals"]
    result = games.groupby("trio_key")[columns].sum()
    result["games"] = games.groupby("trio_key").game_id.nunique()
    result["minutes"] = result.seconds / 60
    result["margin"] = result.points_for - result.points_against
    result["raw"] = 2880 * result.margin / result.seconds
    return result


def baseline(intervals):
    seconds = intervals.duration_seconds.sum()
    return (
        2880 * (intervals.points_for.sum() - intervals.points_against.sum()) / seconds
        if seconds > 0
        else 0.0
    )


def adjusted(raw, minutes, prior, strength):
    return (minutes * raw + strength * prior) / (minutes + strength)


def calibration(games, intervals):
    """Tune on chronological middle 25%, audit on untouched final 25%.

    No future outcomes enter a candidate's training rates or baseline. Validation
    errors weight overlapping trio observations by exposure, not independence.
    """
    schedule = (
        games[["game_id", "game_date"]].drop_duplicates().sort_values(["game_date", "game_id"])
    )
    count = len(schedule)
    if count < 40:
        return {"available": False, "reason": "At least 40 covered games are needed to calibrate."}
    first, second = count // 2, count * 3 // 4
    train_ids = schedule.game_id.iloc[:first]
    validation_ids = schedule.game_id.iloc[first:second]
    test_ids = schedule.game_id.iloc[second:]

    def pairs(past_ids, future_ids):
        past = aggregate(games[games.game_id.isin(past_ids)])
        future = aggregate(games[games.game_id.isin(future_ids)])
        matched = past.join(future, lsuffix="_past", rsuffix="_future", how="inner")
        return matched[
            (matched.minutes_past >= 25)
            & (matched.games_past >= 5)
            & (matched.minutes_future >= 10)
            & (matched.games_future >= 3)
        ]

    validation = pairs(train_ids, validation_ids)
    test = pairs(schedule.game_id.iloc[:second], test_ids)
    if len(validation) < 10 or len(test) < 10:
        return {
            "available": False,
            "reason": "Too few repeated trios for chronological validation.",
        }
    train_prior = baseline(intervals[intervals.game_id.isin(train_ids)])

    def error(frame, prediction):
        return float(
            np.sqrt(np.average((prediction - frame.raw_future) ** 2, weights=frame.minutes_future))
        )

    losses = {
        strength: error(
            validation,
            adjusted(validation.raw_past, validation.minutes_past, train_prior, strength),
        )
        for strength in CANDIDATES
    }
    strength = min(CANDIDATES, key=lambda value: (losses[value], -value))
    test_prior = baseline(intervals[intervals.game_id.isin(schedule.game_id.iloc[:second])])
    return dict(
        available=True,
        strength=strength,
        validation_error=losses[strength],
        raw_error=error(test, test.raw_past),
        baseline_error=error(test, test_prior),
        adjusted_error=error(
            test, adjusted(test.raw_past, test.minutes_past, test_prior, strength)
        ),
        validation_trios=len(validation),
        test_trios=len(test),
        train_games=first,
        validation_games=second - first,
        test_games=count - second,
        training_end=str(schedule.game_date.iloc[first - 1].date()),
        validation_end=str(schedule.game_date.iloc[second - 1].date()),
        test_end=str(schedule.game_date.iloc[-1].date()),
    )


@database_cached(lambda: DATABASE_PATH)
def trio_analysis(team, start=None, end=None):
    data = team_dataset(team)
    intervals, coverage = filter_sample(data, [], start=start, end=end, universe="all")
    games = trio_games(team)
    games = games[games.game_id.isin(intervals.game_id)].copy()
    summary = aggregate(games)
    model = calibration(games, intervals)
    prior = baseline(intervals)
    summary["adjusted"] = (
        adjusted(summary.raw, summary.minutes, prior, model["strength"])
        if model["available"]
        else np.nan
    )
    names = data["players"].set_index("player_id").player_name.to_dict()
    summary["names"] = [
        " | ".join(names.get(int(p), str(p)) for p in key.split("-")) for key in summary.index
    ]
    summary["sample"] = np.where(
        (summary.minutes >= 100) & (summary.games >= 10), "Established exposure", "Exploratory"
    )
    return dict(
        summary=summary.sort_values(["minutes"], ascending=False),
        games=games,
        intervals=intervals,
        coverage=coverage,
        model=model,
        baseline=prior,
        names=names,
    )


def filter_trios(summary, required=(), excluded=(), minutes=100, games=10):
    required, excluded = set(map(str, required or [])), set(map(str, excluded or []))
    mask = [
        required.issubset(key.split("-")) and not excluded.intersection(key.split("-"))
        for key in summary.index
    ]
    return summary.loc[mask][
        (summary.loc[mask].minutes >= (minutes or 0)) & (summary.loc[mask].games >= (games or 0))
    ]


def trio_detail(analysis, key):
    players = set(map(int, key.split("-")))
    if len(players) != 3 or key not in analysis["summary"].index:
        raise ValueError("Select a valid trio.")
    intervals = analysis["intervals"]
    sample = intervals[intervals.players.map(lambda ids: players.issubset(ids))]
    completions = sample.groupby("lineup_key").agg(
        seconds=("duration_seconds", "sum"),
        points_for=("points_for", "sum"),
        points_against=("points_against", "sum"),
        games=("game_id", "nunique"),
        names=("lineup_names", "first"),
    )
    completions["minutes"] = completions.seconds / 60
    completions["raw"] = (
        2880 * (completions.points_for - completions.points_against) / completions.seconds
    )
    completions["share"] = 100 * completions.seconds / sample.duration_seconds.sum()
    completions["partners"] = [
        " + ".join(
            analysis["names"].get(p, str(p))
            for p in sorted(set(map(int, lineup.split("-"))) - players)
        )
        for lineup in completions.index
    ]
    games = analysis["games"][analysis["games"].trio_key == key].sort_values(
        ["game_date", "game_id"]
    )
    confidence = raw_confidence(games)
    return dict(
        completions=completions.sort_values("minutes", ascending=False),
        ci=confidence,
        games=games,
        sample=sample,
    )


def raw_confidence(games):
    """Deterministic whole-game uncertainty, gated by minutes and game count."""
    if games.game_id.nunique() < 10 or games.seconds.sum() < 6000:
        return None
    values = games.sort_values(["game_date", "game_id"])[
        ["seconds", "points_for", "points_against"]
    ].to_numpy(float)
    draws = np.random.default_rng(20260909).integers(0, len(values), (2000, len(values)))
    totals = values[draws].sum(axis=1)
    return np.quantile(2880 * (totals[:, 1] - totals[:, 2]) / totals[:, 0], [0.025, 0.975]).tolist()
