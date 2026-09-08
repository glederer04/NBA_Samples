"""One session-scoped game selection shared by both individual-game pages."""

from dash import Input, Output, State, callback, ctx

from rotation_lab.dashboard.data import get_team_games


def resolve_selection(team, game, saved, linked, trigger):
    if trigger is None:
        selection = linked or saved or {}
        team = selection.get("team", team)
        game = selection.get("game", game)
    options = get_team_games(team) if team else []
    valid = {option["value"] for option in options}
    game = game if game in valid else options[0]["value"] if options else None
    return {"team": team, "game": game}, team, game, options


@callback(
    Output("shared-game-selection", "data"),
    Output("game-team-selector", "value"),
    Output("game-selector", "value"),
    Output("game-selector", "options"),
    Input("game-team-selector", "value"),
    Input("game-selector", "value"),
    State("shared-game-selection", "data"),
    State("game-link-selection", "data"),
)
def synchronize_game_selection(team, game, saved, linked):
    return resolve_selection(team, game, saved, linked, ctx.triggered_id)
