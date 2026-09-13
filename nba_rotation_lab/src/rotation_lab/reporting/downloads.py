"""Browser-native PDF responses, without JavaScript blobs or base64 payloads."""

from io import BytesIO
from math import isfinite
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, render_template_string, request, send_file

from rotation_lab.config import DATABASE_PATH
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.dashboard.data import get_game_review, get_planner_recommendations
from rotation_lab.dashboard.game_context import enrich_game_report
from rotation_lab.modeling import LineupAllocation, project_rotation_plan
from rotation_lab.reporting import generate_game_report_bytes, generate_scenario_report_bytes

reports = Blueprint("reports", __name__, url_prefix="/reports")


def scenario_allocations(
    team: str, keys: list[str], minutes: list[float]
) -> list[LineupAllocation]:
    """Validate transport inputs, then use the existing basketball projection model."""
    if len(keys) != len(minutes) or not 1 <= len(keys) <= 3:
        raise ValueError("Select one to three lineups with planned minutes.")
    if any(not isfinite(value) or value <= 0 for value in minutes):
        raise ValueError("Planned minutes must be finite and greater than zero.")
    pool = {row.lineup_key: row for row in get_planner_recommendations(team, limit=50)}
    if any(key not in pool for key in keys):
        raise ValueError("A selected lineup is unavailable for this team. Refresh the plan.")
    allocations = [
        LineupAllocation(pool[key], value) for key, value in zip(keys, minutes, strict=True)
    ]
    return allocations


def scenario_query(keys: list[str], minutes: list[float]) -> str:
    """Encode repeated lineup/minute parameters in their selected order."""
    return urlencode([("lineup", key) for key in keys] + [("minutes", value) for value in minutes])


@database_cached(lambda: DATABASE_PATH)
def game_pdf(team: str, game_id: str) -> tuple[bytes, str]:
    data = get_game_review(team, game_id)
    if data is None:
        raise LookupError("This game is unavailable for the selected team.")
    return generate_game_report_bytes(
        data=enrich_game_report(data)
    ), f"{team}_{game_id}_game_report.pdf"


@database_cached(lambda: DATABASE_PATH)
def scenario_pdf(team: str, keys: list[str], minutes: list[float]) -> tuple[bytes, str]:
    allocations = scenario_allocations(team, keys, minutes)
    projection = project_rotation_plan(allocations)
    return (
        generate_scenario_report_bytes(allocations=allocations, projection=projection),
        f"{team}_rotation_scenario_report.pdf",
    )


def pdf_response(payload: tuple[bytes, str]) -> Response:
    data, filename = payload
    response = send_file(
        BytesIO(data),
        mimetype="application/pdf",
        download_name=filename,
        as_attachment=request.args.get("view") != "1",
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def report_error(message: str, status: int) -> tuple[str, int]:
    """Errors open separately, keeping the user's dashboard selections intact."""
    return render_template_string(
        """<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Report unavailable</title>
    <body style="margin:0;background:#eef2f6;color:#182235;font-family:system-ui,sans-serif">
    <main style="max-width:540px;margin:10vh auto;padding:32px;background:white;border-radius:12px">
    <p style="font-size:12px;color:#2366d1">NBA ROTATION LAB</p><h1>Report unavailable</h1>
    <p>{{ message }}</p><p>Return to your dashboard tab, check the selection, and try again.</p>
    <a href="/" style="color:#2366d1">Open Rotation Lab</a></main></body></html>""",
        message=message,
    ), status


@reports.get("/game/<team>/<game_id>.pdf")
def download_game(team: str, game_id: str):
    try:
        return pdf_response(game_pdf(team.upper(), game_id))
    except LookupError as error:
        return report_error(str(error), 404)
    except Exception:
        current_app.logger.exception("Game PDF export failed")
        return report_error("The PDF could not be generated. Please retry in a moment.", 503)


@reports.get("/scenario/<team>.pdf")
def download_scenario(team: str):
    try:
        keys = request.args.getlist("lineup")
        minutes = [float(value) for value in request.args.getlist("minutes")]
        return pdf_response(scenario_pdf(team.upper(), keys, minutes))
    except ValueError as error:
        return report_error(str(error), 400)
    except Exception:
        current_app.logger.exception("Scenario PDF export failed")
        return report_error("The PDF could not be generated. Please retry in a moment.", 503)


@reports.post("/player-plan.pdf")
def download_player_plan():
    """POST the exact saved snapshot; no long URLs, client blobs or re-optimization."""
    import json

    from rotation_lab.reporting.player_plan_report import generate_player_plan_report_bytes

    if request.content_length is None or request.content_length > 300_000:
        return report_error("The saved plan is missing or exceeds the report size limit.", 413)
    try:
        plan = json.loads(request.form.get("plan", ""))
        data = generate_player_plan_report_bytes(plan)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        return report_error("This saved plan is invalid. Rebuild it in Scenario Planner.", 400)
    return pdf_response((data, f"{plan['request']['team']}_{plan['id']}_player_minute_plan.pdf"))
