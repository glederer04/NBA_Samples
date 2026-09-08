"""Interactive player Rotation Timeline page."""

from collections import defaultdict
from uuid import uuid4

import plotly.graph_objects as go
from dash import (
    Input,
    Output,
    callback,
    dcc,
    html,
    register_page,
)

from rotation_lab.dashboard.components import (
    build_period_markers,
    format_period_clock,
    format_signed,
    metric_card,
)
from rotation_lab.dashboard.components import get_team_options as get_dashboard_teams
from rotation_lab.dashboard.data import (
    get_rotation_timeline,
    get_team_games,
)

register_page(
    __name__,
    path="/rotations",
    name="Rotation Timeline",
    title="Rotation Timeline | NBA Rotation Lab",
)

TEAM_OPTIONS = get_dashboard_teams()
TEAM_VALUES = [option["value"] for option in TEAM_OPTIONS]
DEFAULT_TEAM = "NYK" if "NYK" in TEAM_VALUES else TEAM_VALUES[0] if TEAM_VALUES else None
DEFAULT_GAME_OPTIONS = get_team_games(DEFAULT_TEAM) if DEFAULT_TEAM else []
DEFAULT_GAME = DEFAULT_GAME_OPTIONS[0]["value"] if DEFAULT_GAME_OPTIONS else None


def layout():
    return html.Div(
        [
            dcc.Store(id="game-link-selection", data={"instance": str(uuid4())}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "ROTATION MANAGEMENT",
                                className="eyebrow",
                            ),
                            html.H1(
                                "Rotation Timeline",
                                className="page-title",
                            ),
                            html.P(
                                "Player stint timing, substitution patterns, "
                                "and rotation depth across the full game.",
                                className="page-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label(
                                        "TEAM",
                                        htmlFor="game-team-selector",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="game-team-selector",
                                        options=TEAM_OPTIONS,
                                        value=DEFAULT_TEAM,
                                        clearable=False,
                                        maxHeight=360,
                                    ),
                                ],
                                className="rotation-filter team",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "GAME",
                                        htmlFor="game-selector",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="game-selector",
                                        options=DEFAULT_GAME_OPTIONS,
                                        value=DEFAULT_GAME,
                                        clearable=False,
                                        maxHeight=360,
                                    ),
                                ],
                                className="rotation-filter game",
                            ),
                        ],
                        className="rotation-filter-row",
                    ),
                ],
                className="page-header rotation-page-header",
            ),
            html.Div(
                id="rotation-metrics",
                className="metric-grid",
            ),
            html.Div(
                [
                    html.Div(
                        "PLAYER STINTS",
                        className="section-eyebrow",
                    ),
                    html.H2(
                        "Full-Game Rotation Map",
                        className="section-title",
                    ),
                    html.P(
                        "Each bar represents one continuous player stint. "
                        "Vertical markers show quarter and overtime starts. "
                        "Green = positive, gray = even, red = negative team +/- during that stint. "
                        "Hover for the exact margin; color intensity is scaled within this game.",
                        className="section-description",
                    ),
                    dcc.Graph(
                        id="rotation-timeline-chart",
                        config={
                            "displayModeBar": False,
                            "responsive": True,
                        },
                    ),
                ],
                className="panel rotation-chart-panel",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "SUBSTITUTION LOG",
                                className="section-eyebrow",
                            ),
                            html.H2(
                                "Recorded Changes",
                                className="section-title",
                            ),
                            html.Div(
                                id="substitution-log",
                            ),
                        ],
                        className="panel substitution-panel",
                    ),
                    html.Div(
                        [
                            html.Div(
                                "ROTATION READOUT",
                                className="section-eyebrow",
                            ),
                            html.H2(
                                "Operational Notes",
                                className="section-title",
                            ),
                            html.Div(
                                id="rotation-readout",
                            ),
                        ],
                        className="panel insight-panel",
                    ),
                ],
                className="rotation-lower-grid",
            ),
        ],
        className="page-content",
    )


def update_rotation_games(
    team_abbreviation: str | None,
    current_game_id: str | None,
) -> tuple[list[dict[str, str]], str | None]:
    """Update available games after a team selection."""

    if team_abbreviation is None:
        return [], None

    options = get_team_games(team_abbreviation)
    game_values = [option["value"] for option in options]

    selected_game = (
        current_game_id
        if current_game_id in game_values
        else game_values[0]
        if game_values
        else None
    )

    return options, selected_game


@callback(
    Output("rotation-metrics", "children"),
    Output("rotation-timeline-chart", "figure"),
    Output("substitution-log", "children"),
    Output("rotation-readout", "children"),
    Input("game-team-selector", "value"),
    Input("game-selector", "value"),
)
def update_rotation_timeline(
    team_abbreviation: str | None,
    game_id: str | None,
) -> tuple:
    """Update the Rotation Timeline page."""

    if team_abbreviation is None or game_id is None:
        return empty_rotation_timeline()

    data = get_rotation_timeline(
        team_abbreviation=team_abbreviation,
        game_id=game_id,
    )

    if data is None:
        return empty_rotation_timeline()

    player_ids = {int(row[0]) for row in data["stints"]}
    player_stint_count = len(data["stints"])
    substitution_count = len(data["substitutions"])
    game_minutes = data["game_end_seconds"] / 60

    metrics = [
        metric_card(
            label="PLAYERS USED",
            value=str(len(player_ids)),
            detail="Players with recorded court time",
        ),
        metric_card(
            label="PLAYER STINTS",
            value=str(player_stint_count),
            detail="Continuous court-time windows",
        ),
        metric_card(
            label="SUBSTITUTIONS",
            value=str(substitution_count),
            detail="Play-by-play substitution events",
        ),
        metric_card(
            label="LINEUPS USED",
            value=str(data["lineups_used"]),
            detail=(f"{data['lineup_changes']} lineup changes"),
        ),
        metric_card(
            label="GAME LENGTH",
            value=f"{game_minutes:.0f} MIN",
            detail=(f"{data['result']} {data['points_for']}-{data['points_against']}"),
        ),
    ]

    figure = build_rotation_figure(
        stints=data["stints"],
        game_end_seconds=data["game_end_seconds"],
    )
    substitutions = build_substitution_log(data["substitutions"])
    readout = build_rotation_readout(data)

    return (
        metrics,
        figure,
        substitutions,
        readout,
    )


def build_rotation_figure(
    stints: list[tuple],
    game_end_seconds: float,
) -> go.Figure:
    """Create a horizontal player-stint timeline."""

    player_totals: defaultdict[str, float] = defaultdict(float)

    for stint in stints:
        player_totals[str(stint[1])] += float(stint[5])

    player_order = [
        player_name
        for player_name, _minutes in sorted(
            player_totals.items(),
            key=lambda item: (
                item[1],
                item[0],
            ),
            reverse=True,
        )
    ]

    margins = [int(stint[6]) if len(stint) > 6 else 0 for stint in stints]
    scale_limit = max(5, max((abs(value) for value in margins), default=0))

    figure = go.Figure()

    # A single trace preserves every stint and tooltip while avoiding per-stint Plotly overhead.
    figure.add_trace(
        go.Bar(
            x=[float(stint[5]) / 60 for stint in stints],
            y=[str(stint[1]) for stint in stints],
            base=[float(stint[3]) / 60 for stint in stints],
            orientation="h",
            marker={
                "color": margins,
                "colorscale": [[0, "#b74754"], [0.5, "#d3d9e1"], [1, "#16855b"]],
                "cmin": -scale_limit,
                "cmax": scale_limit,
                "showscale": False,
                "line": {"color": "#ffffff", "width": 1},
            },
            customdata=[
                [
                    int(stint[2]),
                    float(stint[3]) / 60,
                    float(stint[4]) / 60,
                    float(stint[5]) / 60,
                    int(stint[6]) if len(stint) > 6 else 0,
                ]
                for stint in stints
            ],
            hovertemplate=(
                "<b>%{y}</b><br>Stint %{customdata[0]}<br>"
                "Game minute: %{customdata[1]:.2f}-%{customdata[2]:.2f}<br>"
                "Duration: %{customdata[3]:.2f} min<br>Team +/- during stint: "
                "%{customdata[4]:+d}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    markers = build_period_markers(game_end_seconds)

    for marker_seconds, _marker_label in markers[1:]:
        figure.add_vline(
            x=marker_seconds / 60,
            line_width=1,
            line_dash="dash",
            line_color="#9aa6b5",
        )

    tick_values = [marker_seconds / 60 for marker_seconds, _label in markers]
    tick_text = [marker_label for _seconds, marker_label in markers]

    figure.update_layout(
        barmode="overlay",
        height=max(
            440,
            len(player_order) * 38 + 100,
        ),
        margin={
            "l": 145,
            "r": 25,
            "t": 30,
            "b": 55,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f7f9fc",
        xaxis={
            "title": "Game timeline",
            "range": [
                0,
                game_end_seconds / 60,
            ],
            "tickmode": "array",
            "tickvals": tick_values,
            "ticktext": tick_text,
            "gridcolor": "#e0e6ed",
            "zeroline": False,
        },
        yaxis={
            "title": None,
            "categoryorder": "array",
            "categoryarray": list(reversed(player_order)),
            "gridcolor": "#e8edf3",
        },
        hoverlabel={
            "bgcolor": "#111b2c",
            "font_color": "#ffffff",
        },
    )

    return figure


def build_substitution_log(
    substitutions: list[tuple],
) -> html.Table:
    """Create the play-by-play substitution table."""

    rows = []

    for substitution in substitutions:
        (
            period,
            clock,
            elapsed_deciseconds,
            player_id,
            player_name,
            description,
        ) = substitution

        rows.append(
            html.Tr(
                [
                    html.Td(
                        format_period_clock(
                            int(period),
                            int(elapsed_deciseconds),
                        )
                    ),
                    html.Td(str(player_name or "Team")),
                    html.Td(str(description)),
                    html.Td(str(player_id) if player_id else "—"),
                ]
            )
        )

    if not rows:
        return html.Table(
            html.Tbody(html.Tr(html.Td("No substitution events are available."))),
            className="data-table",
        )

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Game Clock"),
                        html.Th("Player"),
                        html.Th("Event"),
                        html.Th("Player ID"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="data-table substitution-table",
    )


def build_rotation_readout(
    data: dict,
) -> html.Div:
    """Create deterministic rotation-management notes."""

    if not data["stints"]:
        return html.Div("No player stints are available for this game.", className="empty-state")

    player_minutes: defaultdict[str, float] = defaultdict(float)
    player_stint_counts: defaultdict[str, int] = defaultdict(int)

    for stint in data["stints"]:
        player_name = str(stint[1])
        player_minutes[player_name] += float(stint[5]) / 60
        player_stint_counts[player_name] += 1

    minutes_leader = max(
        player_minutes,
        key=lambda player_name: player_minutes[player_name],
    )
    most_fragmented_player = max(
        player_stint_counts,
        key=lambda player_name: player_stint_counts[player_name],
    )

    location = "home" if data["team_location"] == "home" else "road"

    return html.Div(
        [
            insight_row(
                "01",
                (
                    f"{minutes_leader} led the rotation "
                    f"with {player_minutes[minutes_leader]:.1f} "
                    f"minutes."
                ),
            ),
            insight_row(
                "02",
                (
                    f"{most_fragmented_player} had "
                    f"{player_stint_counts[most_fragmented_player]} "
                    f"separate court-time stints."
                ),
            ),
            insight_row(
                "03",
                (
                    f"The staff used {data['lineups_used']} "
                    f"unique lineups with "
                    f"{data['lineup_changes']} lineup changes."
                ),
            ),
            insight_row(
                "04",
                (
                    f"The {location} rotation finished "
                    f"{format_signed(data['plus_minus'])} "
                    f"against {data['opponent']}."
                ),
            ),
        ]
    )


def insight_row(
    number: str,
    text: str,
) -> html.Div:
    """Create one numbered rotation insight."""

    return html.Div(
        [
            html.Div(
                number,
                className="insight-number",
            ),
            html.P(text),
        ],
        className="insight-row",
    )


def empty_rotation_timeline() -> tuple:
    """Return empty Rotation Timeline outputs."""

    message = html.Div(
        "No rotation timeline is available.",
        className="empty-state",
    )

    return (
        [],
        go.Figure(),
        message,
        message,
    )
