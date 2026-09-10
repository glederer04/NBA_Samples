"""One shared dataset for the single-game UI and its PDF export."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.dashboard.cache import database_cached
from rotation_lab.dashboard.impact import filter_sample, summarize, team_dataset
from rotation_lab.dashboard.trios import aggregate, trio_games


@database_cached(lambda: DATABASE_PATH)
def game_context(team, game_id):
    data = team_dataset(team)
    intervals, coverage = filter_sample(data, [], universe="all", game_id=game_id)
    players = []
    for person in data["players"].itertuples():
        result = summarize(intervals, person.player_id, bootstrap=False)
        if result["totals"][0][0] > 0:
            players.append(
                dict(
                    name=person.player_name,
                    player=person.player_id,
                    on_minutes=result["totals"][0][0] / 60,
                    off_minutes=result["totals"][1][0] / 60,
                    on=result["rates"][0][0],
                    off=result["rates"][1][0],
                    swing=result["swing"][0],
                )
            )
    players.sort(key=lambda row: (-row["on_minutes"], row["name"]))
    games = trio_games(team)
    games = games[(games.game_id == game_id) & games.game_id.isin(intervals.game_id)]
    trios = []
    names = data["players"].set_index("player_id").player_name.to_dict()
    for key, row in aggregate(games).sort_values("minutes", ascending=False).head(3).iterrows():
        members = set(map(int, key.split("-")))
        sample = intervals[intervals.players.map(lambda ids, m=members: m.issubset(ids))]
        units = sample.groupby("lineup_key").duration_seconds.sum().sort_values(ascending=False)
        partners = sorted(set(map(int, units.index[0].split("-"))) - members)
        trios.append(
            dict(
                key=key,
                names=" | ".join(names[p] for p in sorted(members)),
                minutes=float(row.minutes),
                points_for=int(row.points_for),
                points_against=int(row.points_against),
                margin=int(row.margin),
                raw=float(row.raw),
                partners=" + ".join(names[p] for p in partners),
                partner_minutes=float(units.iloc[0]) / 60,
            )
        )
    return dict(players=players, trios=trios, coverage=coverage)


def enrich_game_report(data):
    """Attach the same compact player/core evidence used on Game Review."""
    return {**data, "player_context": game_context(data["team_abbreviation"], data["game_id"])}
