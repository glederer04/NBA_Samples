"""Immutable, versioned plan snapshots shared by the UI and PDF renderer."""

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime

import numpy as np

from rotation_lab.modeling.planner_evidence import MODEL_VERSION
from rotation_lab.modeling.player_planner import VERSION, digest, validate_schedule


def plan_snapshot(request, units, result, evidence, prior=None):
    schedule = result["schedule"]
    lookup = {u["key"]: u for u in units}
    counts = Counter(schedule)
    weights = {key: count / 48 for key, count in counts.items()}
    draws = sum(weight * lookup[key]["draws"] for key, weight in weights.items())
    mu = sum(weight * lookup[key]["mu"] for key, weight in weights.items())
    saved_units = [{k: v for k, v in lookup[key].items() if k != "draws"} for key in sorted(counts)]
    segments = []
    for t, key in enumerate(schedule):
        if not segments or segments[-1]["key"] != key or t % 12 == 0:
            segments.append(dict(start=t, end=t + 1, key=key))
        else:
            segments[-1]["end"] = t + 1
    players = []
    sets = [set(lookup[key]["players"]) for key in schedule]
    for p in request["players"]:
        presence = [str(p["id"]) in s for s in sets]
        stints = []
        for t, playing in enumerate(presence):
            if playing:
                if not stints or stints[-1][1] != t or t % 12 == 0:
                    stints.append([t, t + 1])
                else:
                    stints[-1][1] = t + 1
        minutes = sum(presence)
        players.append(
            {
                **p,
                "assigned": minutes,
                "binding": "At minimum"
                if minutes == p["min"]
                else "At maximum"
                if minutes == p["max"]
                else "Within range",
                "stints": stints,
                "longest": max((b - a for a, b in stints), default=0),
            }
        )
    pair_minutes = [
        {
            "players": pair["players"],
            "kind": pair["kind"],
            "together": sum(set(map(str, pair["players"])).issubset(s) for s in sets),
        }
        for pair in request.get("pairs", [])
    ]
    saved = dict(
        version=VERSION,
        model_version=MODEL_VERSION,
        dataset=evidence["dataset"],
        created=datetime.now(UTC).isoformat(),
        request=deepcopy(request),
        request_id=digest(request),
        schedule=schedule,
        segments=segments,
        players=players,
        units=saved_units,
        mu=float(mu),
        interval=np.quantile(draws, [0.025, 0.975]).tolist(),
        baseline=evidence["baseline"],
        difference=float(mu - evidence["baseline"]),
        difference_interval=np.quantile(draws - evidence["prior_draws"], [0.025, 0.975]).tolist(),
        established=sum(
            n
            for key, n in counts.items()
            if lookup[key]["minutes"] >= 100 and lookup[key]["games"] >= 10
        )
        / 48
        * 100,
        observed=sum(n for key, n in counts.items() if lookup[key]["minutes"] > 0) / 48 * 100,
        substitutions=sum(len(sets[t] - sets[t - 1]) for t in range(1, 48)),
        pairs=pair_minutes,
        role_minutes={
            role: sum(
                any(p.get(role) and str(p["id"]) in members for p in request["players"])
                for members in sets
            )
            for role in ("handler", "interior", "creator")
            if any(p.get(role) for p in request["players"])
        },
        audit=evidence["audit"],
        season=evidence["season"],
        data_start=evidence["start"],
        data_end=evidence["end"],
        solver={k: v for k, v in result.items() if k != "schedule"},
    )
    if prior and prior["request"]["team"] == request["team"]:
        saved["comparison"] = {
            "id": prior["id"],
            "created": prior["created"],
            "same_constraints": prior["request_id"] == digest(request),
            "changed_minutes": sum(
                a != b for a, b in zip(schedule, prior["schedule"], strict=True)
            ),
            "mu": prior["mu"],
            "established": prior["established"],
            "substitutions": prior["substitutions"],
            "players": [
                {k: p[k] for k in ("id", "name", "min", "target", "max", "assigned")}
                for p in prior["players"]
            ],
        }
    saved["id"] = digest(saved)
    return saved


def validate_snapshot(plan):
    if not isinstance(plan, dict) or plan.get("version") != VERSION:
        return ["Unsupported plan version. Rebuild this plan in the planner."]
    try:
        if len(plan["units"]) > 48 or len(plan["players"]) > 12:
            return ["Plan is larger than the supported limits."]
        if plan["id"] != digest({k: v for k, v in plan.items() if k != "id"}):
            return ["The saved plan was altered. Rebuild it before exporting."]
        return validate_schedule(plan["request"], plan["units"], plan["schedule"])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError):
        return ["Incomplete saved plan. Rebuild before exporting."]
