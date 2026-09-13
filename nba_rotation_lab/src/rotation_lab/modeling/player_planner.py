"""Bounded, auditable player-minute scheduling on a one-minute regulation grid."""

import json
import math
from hashlib import sha256
from time import monotonic

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

VERSION = "player-planner-1"
SLOTS = 48
PRESETS = {
    "balanced": (1.0, 0.35, 0.18, 1.5),
    "continuity": (0.5, 0.5, 0.75, 2.0),
    "evidence": (0.5, 1.0, 0.3, 2.0),
}


def digest(value):
    def normalize(item):
        if isinstance(item, dict):
            return {k: normalize(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        if isinstance(item, float) and math.isfinite(item) and item.is_integer():
            return int(item)
        return item

    return sha256(
        json.dumps(normalize(value), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()[:16]


def validate_request(request):
    """Fail closed on hard restrictions; no silently rounded minute bounds."""
    errors = []
    if request.get("team") not in {"NYK", "SAS"}:
        errors.append("Choose the Knicks or Spurs.")
    players = request.get("players", [])
    if not isinstance(players, list) or not 5 <= len(players) <= 12:
        return errors + [
            "Select 5–12 available players. This bounded planner supports 12 per plan."
        ]
    ids = [str(p.get("id")) for p in players]
    if len(set(ids)) != len(ids):
        errors.append("Each player can appear only once.")
    for p in players:
        try:
            values = [float(p[k]) for k in ("min", "target", "max", "stint", "rest")]
            if any(
                not isinstance(p[k], (int, float)) or isinstance(p[k], bool)
                for k in ("min", "target", "max", "stint", "rest")
            ):
                raise ValueError
            if not all(math.isfinite(x) and x.is_integer() for x in values):
                raise ValueError
            lo, target, hi, stint, rest = values
            if not (0 <= lo <= target <= hi <= 48 and 1 <= stint <= 48 and 0 <= rest <= 48):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append(
                f"{p.get('name', 'Player')}: use whole-minute ranges 0–48, "
                "min ≤ target ≤ max, stint 1–48 and rest 0–48."
            )
    if errors:
        return errors
    if sum(p["min"] for p in players) > 240:
        errors.append("Minimums exceed 240 player-minutes. Lower one or more minimums.")
    if sum(p["max"] for p in players) < 240:
        errors.append("Maximums total less than 240. Increase caps or add available players.")
    for kind in ("starter", "closer"):
        if sum(bool(p.get(kind)) for p in players) > 5:
            errors.append(f"At most five players can be locked as {kind}s.")
        if any(p.get(kind) and p["max"] < 1 for p in players):
            errors.append(f"A locked {kind} needs at least one allowed minute.")
    for role in request.get("roles", []):
        if role not in {"handler", "interior", "creator"}:
            errors.append("Unknown coverage role.")
        elif not any(p.get(role) for p in players):
            errors.append(f"Assign at least one available {role} before requiring that coverage.")
    for pair in request.get("pairs", []):
        if (
            pair.get("kind") not in {"together", "apart", "stagger"}
            or len(pair.get("players", [])) != 2
        ):
            errors.append("Each pair rule needs two players and together/apart/stagger.")
        elif len(set(map(str, pair["players"]))) != 2 or not set(
            map(str, pair["players"])
        ).issubset(ids):
            errors.append("Pair rules must reference two distinct available players.")
    for lock in request.get("locks", []):
        try:
            start, end = float(lock["start"]), float(lock["end"])
            members = lock["key"].split("-")
            if not (start.is_integer() and end.is_integer() and 0 <= start < end <= 48):
                raise ValueError
            if len(set(members)) != 5 or not set(members).issubset(ids):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError):
            errors.append(
                "Each lineup lock needs five available players and whole-minute "
                "start/end times within 0–48."
            )
    for rest in request.get("windows", []):
        try:
            start, end = float(rest["start"]), float(rest["end"])
            if str(rest["player"]) not in ids or not (
                start.is_integer() and end.is_integer() and 0 <= start < end <= 48
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append("Each rest window needs an available player and whole-minute start/end.")
    if len(request.get("locks", [])) > 48 or len(request.get("windows", [])) > 48:
        errors.append("Use at most 48 locks and 48 rest windows.")
    if request.get("preset", "balanced") not in PRESETS:
        errors.append("Unknown planning priority.")
    return errors


def legal_unit(unit, request):
    members = set(map(str, unit["players"]))
    players = request["players"]
    if len(members) != 5 or not members.issubset(str(p["id"]) for p in players):
        return False
    for role in request.get("roles", []):
        if not any(p.get(role) and str(p["id"]) in members for p in players):
            return False
    for pair in request.get("pairs", []):
        count = len(members.intersection(map(str, pair["players"])))
        if (
            (pair["kind"] == "together" and count == 1)
            or (pair["kind"] == "apart" and count == 2)
            or (pair["kind"] == "stagger" and count == 0)
        ):
            return False
    return True


class Rows:
    def __init__(self):
        self.row, self.col, self.val, self.lo, self.hi = [], [], [], [], []

    def add(self, coefficients, lo=-np.inf, hi=np.inf):
        r = len(self.lo)
        for c, value in coefficients.items():
            if value:
                self.row.append(r)
                self.col.append(c)
                self.val.append(value)
        self.lo.append(lo)
        self.hi.append(hi)

    def constraint(self, size):
        matrix = coo_matrix((self.val, (self.row, self.col)), shape=(len(self.lo), size)).tocsc()
        return LinearConstraint(matrix, self.lo, self.hi)


def solve_rotation(request, candidates, *, time_limit=12, previous=None):
    """Solve only legal units; independently validate every returned incumbent."""
    started = monotonic()
    errors = validate_request(request)
    if errors:
        return {"status": "invalid", "messages": errors}
    units = sorted([u for u in candidates if legal_unit(u, request)], key=lambda u: u["key"])
    if not units:
        return {
            "status": "infeasible",
            "messages": [
                "No candidate lineup meets availability, roles and pair rules. Review those rules "
                "or explicitly enable unobserved combinations."
            ],
        }
    players = request["players"]
    missing = [
        p["name"]
        for p in players
        if p["min"] > 0 and not any(str(p["id"]) in set(map(str, u["players"])) for u in units)
    ]
    if missing:
        return {
            "status": "infeasible",
            "messages": [
                "No legal candidate contains: "
                + ", ".join(missing)
                + ". Expand the pool or change the restrictions; their minimums were not relaxed."
            ],
        }
    L, P, T = len(units), len(players), SLOTS
    # Continuous unit mixtures become a single unit when linked to binary player presence.
    # Five distinct members + one unit per slot makes a fractional mixture of different
    # units incompatible with 0/1 presence; avoids thousands of extra binary variables.
    base_x, base_in, base_out, base_d = L * T, L * T + P * T, L * T + 2 * P * T, L * T + 3 * P * T
    size = base_d + 2 * P
    cost, integer = np.zeros(size), np.zeros(size)
    lower, upper = np.zeros(size), np.ones(size)
    upper[base_d:] = 48
    integer[base_x:base_in] = 1
    score, risk, changes, preference = PRESETS[request.get("preset", "balanced")]
    for unit_index, unit in enumerate(units):
        cost[unit_index * T : (unit_index + 1) * T] = (
            -score * unit["mu"] + risk * unit["sd"] + (3 if unit["minutes"] == 0 else 0)
        ) / 48
    cost[base_in:base_out] = changes
    cost[base_d:] = preference
    rows = Rows()
    incidence = [
        [
            unit_index
            for unit_index, u in enumerate(units)
            if str(p["id"]) in set(map(str, u["players"]))
        ]
        for p in players
    ]
    for t in range(T):
        rows.add({unit_index * T + t: 1 for unit_index in range(L)}, 1, 1)
    wall = [
        t + (2 if t >= 12 else 0) + (15 if t >= 24 else 0) + (2 if t >= 36 else 0) for t in range(T)
    ]
    for p, person in enumerate(players):

        def x(t, p=p):
            return base_x + p * T + t

        for t in range(T):
            rows.add({x(t): -1, **{unit_index * T + t: 1 for unit_index in incidence[p]}}, 0, 0)
            if t:
                rows.add({base_in + p * T + t: 1, x(t): -1, x(t - 1): 1}, lo=0)
                rows.add({base_out + p * T + t: 1, x(t - 1): -1, x(t): 1}, lo=0)
                for s in range(t + 1, T):
                    if wall[s] - (wall[t] - {12: 2, 24: 15, 36: 2}.get(t, 0)) >= person["rest"]:
                        break
                    rows.add({x(s): 1, base_out + p * T + t: 1}, hi=1)
            max_stint = int(person["stint"])
            if t % 12 >= max_stint:
                rows.add({x(s): 1 for s in range(t - max_stint, t + 1)}, hi=max_stint)
        rows.add({x(t): 1 for t in range(T)}, person["min"], person["max"])
        rows.add(
            {**{x(t): 1 for t in range(T)}, base_d + 2 * p: -1, base_d + 2 * p + 1: 1},
            person["target"],
            person["target"],
        )
        if person.get("starter"):
            lower[x(0)] = 1
        if person.get("closer"):
            lower[x(47)] = 1
    keys = {u["key"]: unit_index for unit_index, u in enumerate(units)}
    for lock in request.get("locks", []):
        if lock["key"] not in keys:
            return {
                "status": "infeasible",
                "messages": [
                    "A locked lineup is outside the legal candidate pool. Review its availability, "
                    "roles/pair rules or enable unobserved units."
                ],
            }
        for t in range(int(lock["start"]), int(lock["end"])):
            lower[keys[lock["key"]] * T + t] = 1
    for window in request.get("windows", []):
        p = next(
            i for i, person in enumerate(players) if str(person["id"]) == str(window["player"])
        )
        for t in range(int(window["start"]), int(window["end"])):
            upper[base_x + p * T + t] = 0
    if np.any(lower > upper):
        return {
            "status": "infeasible",
            "messages": ["Opening/closing locks conflict with rest windows."],
        }
    if previous:
        rows.add({keys[k] * T + t: 1 for t, k in enumerate(previous) if k in keys}, hi=44)
    result = milp(
        cost,
        integrality=integer,
        bounds=Bounds(lower, upper),
        constraints=rows.constraint(size),
        options={"time_limit": float(time_limit), "mip_rel_gap": 0.02},
    )
    elapsed = monotonic() - started
    if result.x is None:
        status = "infeasible" if result.status == 2 else "timeout"
        message = (
            "No schedule satisfies these ranges, locks and rest/stint rules in the candidate "
            "pool. Try wider minute ranges, fewer locks, or explicitly include unobserved units."
            if status == "infeasible"
            else "The time limit was reached before finding a feasible schedule. This does not "
            "prove the inputs are impossible. Try a smaller roster/pool or fewer locks."
        )
        return {"status": status, "messages": [message], "seconds": elapsed}
    schedule = [
        units[int(np.argmax(result.x[: L * T].reshape(L, T)[:, t]))]["key"] for t in range(T)
    ]
    violations = validate_schedule(request, units, schedule)
    if violations:
        return {
            "status": "failed",
            "messages": ["Solver result failed independent validation.", *violations],
        }
    return {
        "status": "optimal" if result.status == 0 else "feasible",
        "schedule": schedule,
        "seconds": elapsed,
        "gap": float(result.mip_gap) if getattr(result, "mip_gap", None) is not None else None,
        "candidate_count": L,
        "messages": [
            "All hard constraints passed. "
            + (
                "Optimal within this pool, objective and grid (2% solver tolerance)."
                if result.status == 0
                else "Time limit reached; this feasible plan is not proven optimal."
            )
        ],
    }


def validate_schedule(request, units, schedule):
    """A separate, non-optimization check used for solver incumbents and PDF snapshots."""
    errors = validate_request(request)
    if errors:
        return errors
    lookup = {u["key"]: u for u in units}
    if len(schedule) != 48 or any(k not in lookup for k in schedule):
        return ["The plan must cover 48 one-minute slots using known lineups."]
    sets = [set(map(str, lookup[k]["players"])) for k in schedule]
    if any(not legal_unit(lookup[k], request) for k in schedule):
        errors.append("A lineup violates availability, role coverage or pair rules.")
    wall = [
        t + (2 if t >= 12 else 0) + (15 if t >= 24 else 0) + (2 if t >= 36 else 0)
        for t in range(48)
    ]
    for person in request["players"]:
        on = [str(person["id"]) in s for s in sets]
        if not person["min"] <= sum(on) <= person["max"]:
            errors.append(f"{person['name']}: minute range violated.")
        if person.get("starter") and not on[0] or person.get("closer") and not on[-1]:
            errors.append(f"{person['name']}: opening/closing lock violated.")
        run = 0
        for t, playing in enumerate(on):
            if t % 12 == 0:
                run = 0
            run = run + 1 if playing else 0
            if run > person["stint"]:
                errors.append(f"{person['name']}: maximum continuous stint violated.")
                break
        for t in range(1, 48):
            if on[t - 1] and not on[t]:
                next_on = next((s for s in range(t + 1, 48) if on[s]), None)
                if (
                    next_on is not None
                    and wall[next_on] - (wall[t] - {12: 2, 24: 15, 36: 2}.get(t, 0))
                    < person["rest"]
                ):
                    errors.append(f"{person['name']}: minimum rest violated.")
    for lock in request.get("locks", []):
        if any(schedule[t] != lock["key"] for t in range(int(lock["start"]), int(lock["end"]))):
            errors.append("A locked lineup window changed.")
    for window in request.get("windows", []):
        if any(
            str(window["player"]) in sets[t]
            for t in range(int(window["start"]), int(window["end"]))
        ):
            errors.append("A player played during a locked rest window.")
    return sorted(set(errors))
