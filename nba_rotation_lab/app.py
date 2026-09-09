"""NBA Rotation Lab Dash application."""

import os

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, callback, dcc, html, page_container
from flask import Response, jsonify

from rotation_lab.config import ASSETS_DIR
from rotation_lab.dashboard import game_selection  # noqa: F401
from rotation_lab.dashboard.impact import initialize_impact_views
from rotation_lab.database import connect_database
from rotation_lab.reporting.downloads import reports

initialize_impact_views()

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    assets_folder=str(ASSETS_DIR),
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
    ],
    suppress_callback_exceptions=True,
    title="NBA Rotation Lab",
)

server = app.server
server.register_blueprint(reports)


@server.get("/health")
def health_check() -> tuple[Response, int]:
    """Confirm that the web process and analytical database are ready."""

    try:
        connection = connect_database(read_only=True)

        try:
            result = connection.execute(
                """
                SELECT COUNT(*)
                FROM raw.teams
                """
            ).fetchone()
        finally:
            connection.close()

        if result is None or result[0] == 0:
            raise RuntimeError("database contains no teams")
    except Exception:
        server.logger.exception("NBA Rotation Lab health check failed")

        return jsonify(
            status="unhealthy",
            database="unavailable",
        ), 503

    return jsonify(
        status="ok",
        database="ready",
    ), 200


app.layout = html.Div(
    [
        dcc.Store(id="shared-game-selection", storage_type="session"),
        html.Aside(
            [
                html.Div(
                    [
                        html.Div(
                            "NBA",
                            className="brand-mark",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "ROTATION",
                                    className="brand-title",
                                ),
                                html.Div(
                                    "LAB",
                                    className="brand-subtitle",
                                ),
                            ]
                        ),
                    ],
                    className="brand",
                ),
                html.Nav(
                    [
                        dbc.NavLink(
                            "Executive Overview",
                            id="nav-overview",
                            href="/",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Game Review",
                            id="nav-review",
                            href="/game-review",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Rotation Timeline",
                            id="nav-rotations",
                            href="/rotations",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Lineup Explorer",
                            id="nav-lineups",
                            href="/lineups",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Player Impact",
                            id="nav-impact",
                            href="/player-impact",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Recommendations",
                            id="nav-recommendations",
                            href="/recommendations",
                            active=False,
                        ),
                        dbc.NavLink(
                            "Scenario Planner",
                            id="nav-planner",
                            href="/scenario-planner",
                            active=False,
                        ),
                    ],
                    className="sidebar-nav",
                ),
                html.Div(
                    [
                        html.Div(
                            "DATASET",
                            className="sidebar-label",
                        ),
                        html.Div(
                            [
                                html.Span(className="status-dot"),
                                html.Span(
                                    "Development sample",
                                    className="status-text",
                                ),
                            ],
                            className="status-row",
                        ),
                    ],
                    className="sidebar-status",
                ),
                html.Div(
                    [
                        "NBA Rotation Lab is an independent "
                        "analytics portfolio project. NBA names "
                        "and imagery belong to their respective "
                        "rights holders."
                    ],
                    className="sidebar-footer",
                ),
            ],
            className="sidebar",
        ),
        html.Main(
            page_container,
            className="application-main",
        ),
    ],
    className="application-shell",
)


@callback(
    [
        Output(f"nav-{name}", "active")
        for name in (
            "overview",
            "review",
            "rotations",
            "recommendations",
            "planner",
            "lineups",
            "impact",
        )
    ],
    Input("_pages_location", "pathname"),
)
def active_navigation(pathname):
    """Track Dash page navigation consistently, including Safari history updates."""
    path = (pathname or "/").rstrip("/") or "/"
    return [
        path == "/",
        path == "/game-review" or path.startswith("/game-review/"),
        path == "/rotations",
        path == "/recommendations",
        path == "/scenario-planner",
        path == "/lineups",
        path == "/player-impact",
    ]


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8050")),
        debug=os.getenv("DASH_DEBUG", "false").lower() == "true",
    )
