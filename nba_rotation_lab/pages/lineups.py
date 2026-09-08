"""Interactive five-player Lineup Explorer page."""

from dash import (
    Input,
    Output,
    State,
    callback,
    dash_table,
    dcc,
    html,
    register_page,
)

from rotation_lab.dashboard.components import (
    compact_lineup_names,
    lineup_card,
    metric_card,
)
from rotation_lab.dashboard.components import get_team_options as get_dashboard_teams
from rotation_lab.dashboard.data import (
    get_lineup_explorer,
    get_team_players,
)

register_page(
    __name__,
    path="/lineups",
    name="Lineup Explorer",
    title="Lineup Explorer | NBA Rotation Lab",
)

TEAM_OPTIONS = get_dashboard_teams()
TEAM_VALUES = [option["value"] for option in TEAM_OPTIONS]
DEFAULT_TEAM = "NYK" if "NYK" in TEAM_VALUES else TEAM_VALUES[0] if TEAM_VALUES else None

layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            "LINEUP ANALYSIS",
                            className="eyebrow",
                        ),
                        html.H1(
                            "Lineup Explorer",
                            className="page-title",
                        ),
                        html.P(
                            "Search five-player combinations, compare "
                            "performance, and control for sample size.",
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
                                    htmlFor="lineup-team-selector",
                                    className="filter-label",
                                ),
                                dcc.Dropdown(
                                    id="lineup-team-selector",
                                    options=TEAM_OPTIONS,
                                    value=DEFAULT_TEAM,
                                    clearable=False,
                                    maxHeight=360,
                                ),
                            ],
                            className="lineup-filter team",
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "REQUIRED PLAYERS",
                                    htmlFor="lineup-player-selector",
                                    className="filter-label",
                                ),
                                dcc.Dropdown(
                                    id="lineup-player-selector",
                                    options=(
                                        get_team_players(DEFAULT_TEAM) if DEFAULT_TEAM else []
                                    ),
                                    value=[],
                                    multi=True,
                                    maxHeight=360,
                                    placeholder=("Select players who must appear together"),
                                ),
                            ],
                            className="lineup-filter players",
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "MINIMUM MINUTES",
                                    htmlFor="lineup-minimum-minutes",
                                    className="filter-label",
                                ),
                                dcc.Input(
                                    id="lineup-minimum-minutes",
                                    type="number",
                                    debounce=0.3,
                                    min=0,
                                    step=1,
                                    value=5,
                                    className="minutes-input",
                                ),
                            ],
                            className="lineup-filter minutes",
                        ),
                    ],
                    className="lineup-filter-row",
                ),
            ],
            className="page-header lineup-page-header",
        ),
        html.Div(
            id="lineup-explorer-metrics",
            className="metric-grid lineup-metric-grid",
        ),
        html.Div(
            [
                html.Div(
                    "LINEUP COMPARISON",
                    className="section-eyebrow",
                ),
                html.H2(
                    "Highest-Minute Matching Units",
                    className="section-title",
                ),
                html.Div(
                    id="lineup-explorer-cards",
                    className="lineup-list",
                ),
            ],
            className="panel",
        ),
        html.Div(
            [
                html.Div(
                    "SORTABLE RESULTS",
                    className="section-eyebrow",
                ),
                html.H2(
                    "Complete Lineup Table",
                    className="section-title",
                ),
                html.P(
                    "Click a column heading to sort. The light row below contains filters "
                    "(text or comparisons such as > 10). Names use first initials; "
                    "hover a lineup for full names. PF/PA are points for/against. Boundary pts "
                    "counts scoring by either team at an exact lineup-change timestamp; these "
                    "points are assigned to the ending lineup and flagged for review, not "
                    "counted as errors.",
                    className="section-description",
                ),
                html.Div(
                    id="lineup-explorer-table",
                ),
            ],
            className="panel lineup-table-panel",
        ),
    ],
    className="page-content",
)


@callback(
    Output("lineup-player-selector", "options"),
    Output("lineup-player-selector", "value"),
    Input("lineup-team-selector", "value"),
    State("lineup-player-selector", "value"),
)
def update_player_options(
    team_abbreviation: str | None,
    selected_players: list[str] | None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Update available player filters after a team change."""

    if team_abbreviation is None:
        return [], []

    options = get_team_players(team_abbreviation)
    available_values = {option["value"] for option in options}
    retained_players = [
        player_id for player_id in selected_players or [] if player_id in available_values
    ]

    return options, retained_players


@callback(
    Output("lineup-explorer-metrics", "children"),
    Output("lineup-explorer-cards", "children"),
    Output("lineup-explorer-table", "children"),
    Input("lineup-team-selector", "value"),
    Input("lineup-minimum-minutes", "value"),
    Input("lineup-player-selector", "value"),
)
def update_lineup_explorer(
    team_abbreviation: str | None,
    minimum_minutes: float | None,
    selected_players: list[str] | None,
) -> tuple:
    """Update matching lineup results."""

    if team_abbreviation is None:
        return empty_lineup_results()

    safe_minimum_minutes = max(
        float(minimum_minutes or 0),
        0,
    )

    rows = get_lineup_explorer(
        team_abbreviation=team_abbreviation,
        minimum_minutes=safe_minimum_minutes,
        player_ids=selected_players,
    )

    if not rows:
        return empty_lineup_results()

    positive_lineups = sum(1 for row in rows if int(row[7]) > 0)
    total_minutes = sum(float(row[4]) for row in rows)
    best_plus_minus_row = max(
        rows,
        key=lambda row: (
            float(row[8]),
            float(row[4]),
        ),
    )

    metrics = [
        metric_card(
            label="MATCHING LINEUPS",
            value=str(len(rows)),
            detail="Units satisfying all filters",
        ),
        metric_card(
            label="COMBINED MINUTES",
            value=f"{total_minutes:.1f}",
            detail="Sum of matching lineup minutes",
        ),
        metric_card(
            label="POSITIVE UNITS",
            value=str(positive_lineups),
            detail="Lineups with positive raw plus-minus",
        ),
        metric_card(
            label="BEST PLUS-MINUS / 48",
            value=f"{float(best_plus_minus_row[8]):+.1f}",
            detail=str(best_plus_minus_row[12]).title(),
        ),
    ]

    cards = [
        lineup_card(
            lineup_key=str(row[0]),
            lineup_names=str(row[1]),
            games_used=int(row[2]),
            total_minutes=float(row[4]),
            points_for=int(row[5]),
            points_against=int(row[6]),
            plus_minus=int(row[7]),
            plus_minus_per_48=float(row[8]),
            sample_size_status=str(row[12]),
        )
        for row in rows[:3]
    ]

    table_data: list[
        dict[
            str | float | int,
            str | float | int | bool,
        ]
    ] = [
        {
            "lineup": compact_lineup_names(str(row[1])),
            "games": int(row[2]),
            "stints": int(row[3]),
            "minutes": float(row[4]),
            "points_for": int(row[5]),
            "points_against": int(row[6]),
            "plus_minus": int(row[7]),
            "plus_minus_per_48": float(row[8]),
            "points_for_per_48": float(row[9]),
            "points_against_per_48": float(row[10]),
            "boundary_points": int(row[11]),
            "sample": str(row[12]).title(),
        }
        for row in rows
    ]

    table = dash_table.DataTable(
        id="complete-lineup-table",
        data=table_data,
        tooltip_data=[{"lineup": {"value": str(row[1]), "type": "text"}} for row in rows],
        tooltip_duration=None,
        filter_options={"placeholder_text": "Filter…", "case": "insensitive"},
        columns=[
            {
                "name": "Lineup",
                "id": "lineup",
            },
            {
                "name": "Games",
                "id": "games",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "Stints",
                "id": "stints",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "Minutes",
                "id": "minutes",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
                "format": {
                    "specifier": ".2f",
                },
            },
            {
                "name": "PF",
                "id": "points_for",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "PA",
                "id": "points_against",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "+/-",
                "id": "plus_minus",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "+/- per 48",
                "id": "plus_minus_per_48",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
                "format": {
                    "specifier": "+.2f",
                },
            },
            {
                "name": "PF per 48",
                "id": "points_for_per_48",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
                "format": {
                    "specifier": ".2f",
                },
            },
            {
                "name": "PA per 48",
                "id": "points_against_per_48",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
                "format": {
                    "specifier": ".2f",
                },
            },
            {
                "name": "Boundary pts",
                "id": "boundary_points",
                "type": "numeric",
                "filter_options": {"case": "sensitive"},
            },
            {
                "name": "Sample",
                "id": "sample",
            },
        ],
        sort_action="native",
        sort_mode="multi",
        filter_action="native",
        page_action="native",
        page_size=15,
        style_table={
            "overflowX": "auto",
        },
        style_cell={
            "padding": "12px",
            "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            "minWidth": "80px",
            "width": "90px",
            "maxWidth": "150px",
            "fontSize": "12px",
            "textAlign": "left",
            "whiteSpace": "normal",
            "height": "auto",
        },
        style_cell_conditional=[
            {
                "if": {"column_id": "lineup"},
                "minWidth": "300px",
                "width": "300px",
                "maxWidth": "420px",
            },
            {"if": {"column_id": "sample"}, "minWidth": "120px", "width": "120px"},
        ],
        style_filter={
            "backgroundColor": "#eef3f9",
            "color": "#334155",
            "borderBottom": "2px solid #cbd5e1",
            "padding": "8px",
        },
        style_header={
            "backgroundColor": "#111b2c",
            "color": "#ffffff",
            "fontWeight": "700",
            "border": "0",
        },
        style_data={
            "border": "0",
            "borderBottom": "1px solid #e5eaf0",
        },
        style_data_conditional=[
            {
                "if": {
                    "filter_query": "{plus_minus} > 0",
                    "column_id": "plus_minus",
                },
                "color": "#16855b",
                "fontWeight": "700",
            },
            {
                "if": {
                    "filter_query": "{plus_minus} < 0",
                    "column_id": "plus_minus",
                },
                "color": "#c5424d",
                "fontWeight": "700",
            },
        ],
    )

    return metrics, cards, table


def empty_lineup_results() -> tuple:
    """Return empty Lineup Explorer outputs."""

    message = html.Div(
        "No lineups matched the selected filters.",
        className="empty-state",
    )

    return (
        [],
        message,
        message,
    )
