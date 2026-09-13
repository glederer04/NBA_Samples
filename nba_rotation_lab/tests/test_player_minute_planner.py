"""Independent schedule and report acceptance tests; small cases have known answers."""

import json
from io import BytesIO
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest
from pypdf import PdfReader

from rotation_lab.modeling.planner_plan import plan_snapshot, validate_snapshot
from rotation_lab.modeling.player_planner import (
    solve_rotation,
    validate_request,
    validate_schedule,
)
from rotation_lab.reporting.player_plan_report import generate_player_plan_report_bytes


def case(n=6):
    request = dict(
        team="NYK",
        players=[
            dict(id=str(i), name=f"Player {i}", min=0, target=240 // n, max=48, stint=12, rest=0)
            for i in range(n)
        ],
        preset="balanced",
    )
    units = [
        dict(
            key="-".join(ids),
            players=list(ids),
            mu=0.0,
            sd=0.0,
            minutes=120.0,
            games=20,
            pf=10,
            pa=10,
            draws=np.zeros(200),
            interval=[0.0, 0.0],
            method="Historical shrinkage",
        )
        for ids in combinations([str(i) for i in range(n)], 5)
    ]
    return request, units


def test_five_players_hand_solution_and_repeatability():
    r, u = case(5)
    for p in r["players"]:
        p.update(min=48, target=48)
    a = solve_rotation(r, u, time_limit=2)
    b = solve_rotation(r, u, time_limit=2)
    assert a["schedule"] == b["schedule"] == [u[0]["key"]] * 48
    assert not validate_schedule(r, u, a["schedule"])
    assert sum(sum(p["id"] in k.split("-") for k in a["schedule"]) for p in r["players"]) == 240


@pytest.mark.parametrize(
    "change",
    [{"min": 49}, {"max": -1}, {"target": 1.5}, {"rest": float("nan")}, {"min": "1"}, {"stint": 0}],
)
def test_bad_ranges(change):
    r, u = case()
    r["players"][0].update(change)
    assert validate_request(r)
    assert solve_rotation(r, u)["status"] == "invalid"


def test_capacity_and_roles_and_pair_conflicts():
    r, u = case()
    for p in r["players"]:
        p["max"] = 35
        p["target"] = 35
    assert "240" in " ".join(validate_request(r))
    r, u = case()
    r["roles"] = ["handler"]
    assert validate_request(r)
    r["players"][0]["handler"] = True
    r["pairs"] = [dict(players=["0", "1"], kind="apart")]
    r["players"][1]["min"] = 1
    assert solve_rotation(r, u, time_limit=2)["status"] == "infeasible"


def test_locked_windows_exact_and_alternative():
    r, u = case()
    r["locks"] = [dict(key=u[0]["key"], start=0, end=4)]
    result = solve_rotation(r, u, time_limit=3)
    assert result.get("schedule"), result
    assert result["schedule"][:4] == [u[0]["key"]] * 4
    alternate = solve_rotation(r, u, time_limit=3, previous=result["schedule"])
    assert alternate.get("schedule"), alternate
    assert sum(a != b for a, b in zip(result["schedule"], alternate["schedule"], strict=False)) >= 4
    assert not validate_schedule(r, u, alternate["schedule"])


def test_incompatible_locks_are_not_relaxed():
    r, u = case()
    r["locks"] = [dict(key=u[0]["key"], start=0, end=4), dict(key=u[1]["key"], start=2, end=6)]
    assert solve_rotation(r, u, time_limit=2)["status"] == "infeasible"


def test_rest_and_quarter_break_credit():
    r, u = case()
    p = r["players"][0]
    p["rest"] = 3
    on = next(x["key"] for x in u if "0" in x["players"])
    off = next(x["key"] for x in u if "0" not in x["players"])
    schedule = [on] * 48
    schedule[12] = off
    assert not validate_schedule(r, u, schedule)  # 1 bench minute + 2 quarter-break minutes
    schedule = [on] * 48
    schedule[11] = off
    assert not validate_schedule(r, u, schedule)  # same break, re-enters at Q2
    schedule = [on] * 48
    schedule[10] = off
    assert "rest" in " ".join(validate_schedule(r, u, schedule))
    p["rest"] = 0
    p["stint"] = 6
    assert "stint" in " ".join(validate_schedule(r, u, [on] * 48))


def test_timeout_is_not_infeasibility(monkeypatch):
    import rotation_lab.modeling.player_planner as module

    monkeypatch.setattr(module, "milp", lambda *a, **kw: SimpleNamespace(x=None, status=1))
    r, u = case()
    assert solve_rotation(r, u)["status"] == "timeout"


def test_invalid_incumbent_is_rejected(monkeypatch):
    import rotation_lab.modeling.player_planner as module

    r, u = case()
    r["players"][-1]["min"] = 1
    monkeypatch.setattr(
        module,
        "milp",
        lambda cost, **kw: SimpleNamespace(x=np.zeros(len(cost)), status=1, mip_gap=10),
    )
    assert solve_rotation(r, u)["status"] == "failed"


def snapshot():
    r, u = case(5)
    for p in r["players"]:
        p.update(min=48, target=48)
    evidence = dict(
        dataset="test",
        baseline=0.0,
        prior_draws=np.zeros(200),
        audit={"available": False, "use_context": False, "reason": "Test sample"},
        season="test",
        start="2026-01-01",
        end="2026-02-01",
    )
    return plan_snapshot(r, u, solve_rotation(r, u, time_limit=2), evidence)


def test_snapshot_roundtrip_pdf_and_tamper():
    plan = json.loads(json.dumps(snapshot()))
    assert not validate_snapshot(plan)
    pdf = generate_player_plan_report_bytes(plan)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "240 player-minutes" in text
    assert plan["id"] in text
    assert all(p["name"] in text for p in plan["players"])
    plan["schedule"].pop()
    assert validate_snapshot(plan)
    with pytest.raises(ValueError):
        generate_player_plan_report_bytes(plan)


def test_joint_draws_preserve_covariance():
    r, u = case(6)
    r["players"][0]["target"] = 24
    r["players"][-1]["target"] = 24
    u[0]["draws"] = np.linspace(-5, 5, 200)
    u[1]["draws"] = -u[0]["draws"]
    result = dict(
        status="feasible",
        schedule=[u[0]["key"]] * 24 + [u[1]["key"]] * 24,
        seconds=0,
        messages=["Test"],
        gap=None,
    )
    e = dict(
        dataset="test",
        baseline=0.0,
        prior_draws=np.zeros(200),
        audit={},
        season="test",
        start="a",
        end="b",
    )
    plan = plan_snapshot(r, u, result, e)
    assert plan["interval"] == [0.0, 0.0]


def test_pdf_route_rejects_invalid_snapshot():
    from app import server

    client = server.test_client()
    assert client.post("/reports/player-plan.pdf", data={"plan": "{}"}).status_code == 400
    plan = snapshot()
    response = client.post("/reports/player-plan.pdf", data={"plan": json.dumps(plan)})
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


def test_snapshot_survives_browser_number_normalization():
    from rotation_lab.modeling.player_planner import digest

    plan = snapshot()

    def js_numbers(item):
        if isinstance(item, dict):
            return {k: js_numbers(v) for k, v in item.items()}
        if isinstance(item, list):
            return [js_numbers(v) for v in item]
        if isinstance(item, float) and item.is_integer():
            return int(item)
        return item

    assert not validate_snapshot(js_numbers(plan))
    assert digest({"x": 0.0}) == digest({"x": 0})


def test_audit_keeps_test_outcomes_out_of_tuning():
    import pandas as pd

    from rotation_lab.modeling.planner_evidence import audit_model

    rows = []
    for g in range(48):
        for _interval in range(2):
            rows.append(
                dict(
                    game_id=str(g),
                    game_date=pd.Timestamp("2025-01-01") + pd.Timedelta(days=g),
                    players=[0, 1, 2, 3, 4],
                    lineup_key="0-1-2-3-4",
                    opponent_team_abbreviation="BOS",
                    period=1,
                    team_location="home",
                    pre_margin=0,
                    duration_seconds=1440,
                    points_for=50 + g % 4,
                    points_against=50,
                )
            )
    frame = pd.DataFrame(rows)
    features = ["intercept", "p:0", "opp:BOS", "period:1", "home", "state"]
    a = audit_model(frame, features)
    changed = frame.copy()
    changed.loc[changed.game_id.astype(int) >= 36, "points_for"] += 100
    b = audit_model(changed, features)
    assert a["alpha"] == b["alpha"]
    assert a["tuning_error"] == b["tuning_error"]
    assert a["blended_error"] != b["blended_error"]
    assert a["training_end"] < a["tuning_end"] < a["test_end"]


def test_unseen_candidates_require_opt_in_and_have_no_direct_exposure():
    import pandas as pd

    from rotation_lab.modeling.planner_evidence import candidate_pool

    r, _ = case()
    key = "0-1-2-3-4"
    features = (
        ["intercept"]
        + [f"p:{i}" for i in range(6)]
        + ["opp:BOS"]
        + [f"period:{i}" for i in range(1, 5)]
        + ["home", "state"]
    )
    e = dict(
        keys=[key],
        features=features,
        opponents=["BOS"],
        audit={"use_context": False},
        baseline=2.0,
        prior_draws=np.full(200, 2.0),
        summary=pd.DataFrame([dict(minutes=48, raw=10, games=12, pf=110, pa=100)], index=[key]),
        boot=np.tile([[[48.0, 110.0, 100.0]]], (200, 1, 1)),
    )
    observed = candidate_pool(e, r)
    assert len(observed) == 1 and observed[0]["mu"] == 6.0
    r["unseen"] = True
    expanded = candidate_pool(e, r)
    assert len(expanded) == 6
    unseen = [u for u in expanded if not u["minutes"]]
    assert all(u["games"] == 0 and u["mu"] == 2 for u in unseen)


def test_pdf_form_uses_controlled_value_and_roster_init_is_fast(monkeypatch):
    from rotation_lab.dashboard import player_planning as page

    def no_query(*args):
        raise AssertionError("An empty editor must not query the model")

    monkeypatch.setattr(page, "planner_evidence", no_query)
    assert page.edit_roster([], 0, [], "NYK", None, 20)[0] == []

    def walk(component):
        if getattr(component, "id", None) == "pp-pdf-data":
            return component
        children = getattr(component, "children", [])
        for child in children if isinstance(children, list) else [children]:
            result = walk(child)
            if result is not None:
                return result
        return None

    control = walk(page.layout())
    assert control.type == "hidden" and control.name == "plan" and control.value == ""


def test_trio_completion_prefills_the_actual_five_and_team(monkeypatch):
    from rotation_lab.dashboard import player_planning as page

    monkeypatch.setattr(page, "planner_evidence", lambda team: {"keys": ["1-2-3-4-5"]})
    found = {}

    def walk(component):
        if getattr(component, "id", None) in {"pp-team", "pp-active"}:
            found[component.id] = component.value
        children = getattr(component, "children", [])
        for child in children if isinstance(children, list) else [children]:
            walk(child)

    walk(page.layout(team="SAS", lineup="1-2-3-4-5"))
    assert found == {"pp-team": "SAS", "pp-active": ["1", "2", "3", "4", "5"]}
