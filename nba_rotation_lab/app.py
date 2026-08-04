"""NBA Rotation Lab Dash application."""

import dash_bootstrap_components as dbc
from dash import Dash, html, page_container

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
        port=8050,
        debug=True,
    )
