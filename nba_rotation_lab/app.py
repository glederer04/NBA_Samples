"""NBA Rotation Lab Dash application."""

import os

import dash_bootstrap_components as dbc
from dash import Dash, html, page_container
from flask import Response, jsonify

from rotation_lab.database import connect_database

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
    ],
    suppress_callback_exceptions=True,
    title="NBA Rotation Lab",
)

server = app.server


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
                            href="/",
                            active="exact",
                        ),
                        dbc.NavLink(
                            "Game Review",
                            href="/game-review",
                            active="partial",
                        ),
                        dbc.NavLink(
                            "Recommendations",
                            href="/recommendations",
                            active="exact",
                        ),
                        dbc.NavLink(
                            "Scenario Planner",
                            href="/scenario-planner",
                            active="exact",
                        ),
                        dbc.NavLink(
                            "Lineup Explorer",
                            href="/lineups",
                            active="exact",
                        ),
                        dbc.NavLink(
                            "Rotation Timeline",
                            href="/rotations",
                            active="exact",
                        ),
                    ],
                    className="sidebar-nav",
                ),
                html.Div(
                    [
                        html.Div(
                            "DATA STATUS",
                            className="sidebar-label",
                        ),
                        html.Div(
                            [
                                html.Span(className="status-dot"),
                                html.Span(
                                    "Validated sample",
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

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8050")),
        debug=os.getenv("DASH_DEBUG", "false").lower() == "true",
    )
