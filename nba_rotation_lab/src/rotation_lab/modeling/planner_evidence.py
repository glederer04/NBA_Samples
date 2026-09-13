"""Chronologically audited context estimates and shared game-bootstrap plan evidence."""

from itertools import combinations

import numpy as np
from threadpoolctl import threadpool_limits

from rotation_lab.config import DATABASE_PATH
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.dashboard.impact import filter_sample, team_dataset
from rotation_lab.modeling.player_planner import digest

MODEL_VERSION = "presence-context-ridge-1"
DRAWS = 200


def design(frame, features):
    index = {name: i for i, name in enumerate(features)}
    x = np.zeros((len(frame), len(features)))
    x[:, 0] = 1
    for r, row in enumerate(frame.itertuples()):
        for p in row.players:
            if f"p:{p}" in index:
                x[r, index[f"p:{p}"]] = 1
        for name in (f"opp:{row.opponent_team_abbreviation}", f"period:{min(row.period, 5)}"):
            if name in index:
                x[r, index[name]] = 1
        x[r, index["home"]] = float(row.team_location == "home")
        x[r, index["state"]] = np.clip(row.pre_margin, -20, 20) / 20
    return x


def fit(x, y, w, alpha):
    penalty = np.eye(x.shape[1]) * alpha
    penalty[0, 0] = 1e-8
    return np.linalg.solve(x.T @ (w[:, None] * x) + penalty, x.T @ (w * y))


def unit_summary(frame):
    rows = frame.groupby("lineup_key").agg(
        seconds=("duration_seconds", "sum"),
        pf=("points_for", "sum"),
        pa=("points_against", "sum"),
        games=("game_id", "nunique"),
    )
    rows["minutes"] = rows.seconds / 60
    rows["raw"] = 2880 * (rows.pf - rows.pa) / rows.seconds
    return rows


def team_rate(frame):
    return (
        2880 * (frame.points_for.sum() - frame.points_against.sum()) / frame.duration_seconds.sum()
    )


def historical_prediction(past, future):
    stats = unit_summary(past)
    prior = team_rate(past)
    return np.array(
        [
            (stats.loc[key, "minutes"] * stats.loc[key, "raw"] + 48 * prior)
            / (stats.loc[key, "minutes"] + 48)
            if key in stats.index
            else prior
            for key in future.lineup_key
        ]
    )


def audit_model(frame, features):
    """Fit/tune/test 50/25/25; only earlier outcomes enter each audit fit."""
    schedule = (
        frame[["game_id", "game_date"]].drop_duplicates().sort_values(["game_date", "game_id"])
    )
    ids = schedule.game_id.tolist()
    unavailable = {
        "available": False,
        "use_context": False,
        "reason": "At least 40 fully validated games are required for context calibration.",
    }
    if len(ids) < 40:
        return unavailable
    a, b = len(ids) // 2, len(ids) * 3 // 4
    train, tune, test = [frame[frame.game_id.isin(s)] for s in (ids[:a], ids[a:b], ids[b:])]
    if min(len(train), len(tune), len(test)) == 0:
        return unavailable
    x = design(frame, features)
    y = (
        2880
        * (frame.points_for - frame.points_against).to_numpy()
        / frame.duration_seconds.to_numpy()
    )
    w = frame.duration_seconds.to_numpy() / 60
    train_mask, tune_mask, test_mask = [
        frame.game_id.isin(s).to_numpy() for s in (ids[:a], ids[a:b], ids[b:])
    ]

    def rmse(truth, pred, weights):
        return float(np.sqrt(np.average((truth - pred) ** 2, weights=weights)))

    losses = {}
    for alpha in (100, 500, 2000, 8000):
        beta = fit(x[train_mask], y[train_mask], w[train_mask], alpha)
        losses[alpha] = rmse(y[tune_mask], x[tune_mask] @ beta, w[tune_mask])
    alpha = min(losses, key=lambda k: (losses[k], -k))
    earlier = ~test_mask
    beta = fit(x[earlier], y[earlier], w[earlier], alpha)
    context_prediction = x[test_mask] @ beta
    context_error = rmse(y[test_mask], context_prediction, w[test_mask])
    stats = unit_summary(frame[earlier])
    exposure = np.array(
        [stats.loc[k, "minutes"] if k in stats.index else 0 for k in test.lineup_key]
    )
    raw = np.array([stats.loc[k, "raw"] if k in stats.index else 0 for k in test.lineup_key])
    blended = (exposure * raw + 48 * context_prediction) / (exposure + 48)
    error = rmse(y[test_mask], blended, w[test_mask])
    baseline_error = rmse(y[test_mask], team_rate(frame[earlier]), w[test_mask])
    lineup_error = rmse(y[test_mask], historical_prediction(frame[earlier], test), w[test_mask])
    return dict(
        available=True,
        use_context=error < min(baseline_error, lineup_error),
        alpha=alpha,
        context_error=context_error,
        blended_error=error,
        baseline_error=baseline_error,
        lineup_error=lineup_error,
        tuning_error=losses[alpha],
        training_end=str(train.game_date.max().date()),
        tuning_end=str(tune.game_date.max().date()),
        test_end=str(test.game_date.max().date()),
        train_games=a,
        tune_games=b - a,
        test_games=len(ids) - b,
        reason="Context model must beat both simple baselines on untouched later intervals.",
    )


@database_cached(lambda: DATABASE_PATH)
def planner_evidence(team):
    dataset = team_dataset(team)
    frame, coverage = filter_sample(dataset, [], universe="all")
    if frame.empty:
        raise ValueError("No fully validated games are available for this team.")
    # Use one season for an actionable roster/model; never silently combine seasons.
    latest_season = dataset["games"].sort_values("game_date").season_id.iloc[-1]
    ids = dataset["games"].loc[dataset["games"].season_id == latest_season, "game_id"]
    frame = (
        frame[frame.game_id.isin(ids)]
        .sort_values(["game_date", "game_id", "interval_number"])
        .copy()
    )
    frame["pre_margin"] = (
        frame.groupby("game_id")["points_for"].cumsum()
        - frame.groupby("game_id")["points_against"].cumsum()
        - (frame.points_for - frame.points_against)
    )
    features = ["intercept"] + [
        f"p:{p}" for p in sorted({int(p) for ids in frame.players for p in ids})
    ]
    features += [f"opp:{o}" for o in sorted(frame.opponent_team_abbreviation.unique())]
    features += [f"period:{p}" for p in range(1, 6)] + ["home", "state"]
    with threadpool_limits(limits=1):
        audit = audit_model(frame, features)
        x = design(frame, features)
        y = (
            2880
            * (frame.points_for - frame.points_against).to_numpy()
            / frame.duration_seconds.to_numpy()
        )
        w = frame.duration_seconds.to_numpy() / 60
        alpha = audit.get("alpha", 2000)
        beta = fit(x, y, w, alpha)
        game_ids = frame.game_id.drop_duplicates().tolist()
        game_index = {g: i for i, g in enumerate(game_ids)}
        grams, rhs = [], []
        for g in game_ids:
            mask = (frame.game_id == g).to_numpy()
            grams.append(x[mask].T @ (w[mask, None] * x[mask]))
            rhs.append(x[mask].T @ (w[mask] * y[mask]))
        grams, rhs = np.array(grams), np.array(rhs)
        rng = np.random.default_rng(20260912)
        counts = np.array(
            [
                np.bincount(rng.integers(0, len(game_ids), len(game_ids)), minlength=len(game_ids))
                for _ in range(DRAWS)
            ]
        )
        penalty = np.eye(len(features)) * alpha
        penalty[0, 0] = 1e-8
        betas = np.linalg.solve(
            np.einsum("dg,gij->dij", counts, grams) + penalty, (counts @ rhs)[..., None]
        )[..., 0]
    summary = unit_summary(frame)
    keys = list(summary.index)
    key_index = {k: i for i, k in enumerate(keys)}
    totals = np.zeros((len(game_ids), len(keys), 3))
    for row in frame.itertuples():
        totals[game_index[row.game_id], key_index[row.lineup_key]] += [
            row.duration_seconds / 60,
            row.points_for,
            row.points_against,
        ]
    boot = np.einsum("dg,gki->dki", counts, totals)
    team_boot = boot.sum(axis=1)
    prior_draws = 48 * (team_boot[:, 1] - team_boot[:, 2]) / team_boot[:, 0]
    names = dataset["players"].set_index("player_id").player_name.to_dict()
    roster = []
    for p in sorted({int(p) for ids in frame.players for p in ids}):
        sample = frame[frame.players.map(lambda members, p=p: p in members)]
        roster.append(
            dict(
                id=str(p),
                name=names[p],
                minutes=float(sample.duration_seconds.sum() / 60),
                games=int(sample.game_id.nunique()),
            )
        )
    roster.sort(key=lambda p: (-p["minutes"], p["name"]))
    signature = digest(
        dict(
            team=team,
            season=str(latest_season),
            games=game_ids,
            intervals=frame[
                [
                    "game_id",
                    "lineup_key",
                    "period",
                    "duration_seconds",
                    "points_for",
                    "points_against",
                ]
            ]
            .astype(str)
            .values.tolist(),
            version=MODEL_VERSION,
        )
    )
    return dict(
        team=team,
        roster=roster,
        summary=summary,
        features=features,
        beta=beta,
        betas=betas,
        keys=keys,
        boot=boot,
        baseline=float(team_rate(frame)),
        prior_draws=prior_draws,
        audit=audit,
        opponents=sorted(frame.opponent_team_abbreviation.unique()),
        dataset=signature,
        season=str(latest_season),
        games=len(game_ids),
        start=str(frame.game_date.min().date()),
        end=str(frame.game_date.max().date()),
        coverage=coverage,
    )


def candidate_pool(evidence, request):
    """Never fabricate direct exposure; unseen candidates require explicit opt-in."""
    active = sorted(int(p["id"]) for p in request["players"])
    observed = {
        tuple(map(int, k.split("-"))): k
        for k in evidence["keys"]
        if set(map(int, k.split("-"))).issubset(active)
    }
    members = list(combinations(active, 5)) if request.get("unseen") else sorted(observed)
    lookup = {k: i for i, k in enumerate(evidence["keys"])}
    features = {k: i for i, k in enumerate(evidence["features"])}
    units = []
    context = request.get("opponent", "average")
    for ids in members:
        key = "-".join(map(str, ids))
        design_row = np.zeros(len(features))
        design_row[0] = 1
        for p in ids:
            if f"p:{p}" in features:
                design_row[features[f"p:{p}"]] = 1
        if context != "average" and f"opp:{context}" in features:
            design_row[features[f"opp:{context}"]] = 1
        elif context == "average":
            for opponent in evidence["opponents"]:
                design_row[features[f"opp:{opponent}"]] = 1 / len(evidence["opponents"])
        for period in range(1, 5):
            design_row[features[f"period:{period}"]] = 0.25
        design_row[features["home"]] = {"home": 1, "away": 0, "neutral": 0.5}.get(
            request.get("venue"), 0.5
        )
        use_context = evidence["audit"]["use_context"]
        prior = float(design_row @ evidence["beta"]) if use_context else evidence["baseline"]
        prior_draws = evidence["betas"] @ design_row if use_context else evidence["prior_draws"]
        if key in lookup:
            row = evidence["summary"].loc[key]
            M = float(row.minutes)
            mu = (M * float(row.raw) + 48 * prior) / (M + 48)
            samples = evidence["boot"][:, lookup[key], :]
            draws = (48 * (samples[:, 1] - samples[:, 2]) + 48 * prior_draws) / (samples[:, 0] + 48)
            games, pf, pa = int(row.games), int(row.pf), int(row.pa)
        else:
            M, games, pf, pa = 0.0, 0, 0, 0
            mu, draws = prior, prior_draws
        units.append(
            dict(
                key=key,
                players=list(map(str, ids)),
                minutes=M,
                games=games,
                pf=pf,
                pa=pa,
                mu=float(mu),
                sd=float(np.std(draws)),
                draws=np.asarray(draws),
                interval=np.quantile(draws, [0.025, 0.975]).tolist(),
                method="Context blend"
                if use_context and M
                else "Context only"
                if use_context
                else "Historical shrinkage"
                if M
                else "Team baseline only",
            )
        )
    return units
