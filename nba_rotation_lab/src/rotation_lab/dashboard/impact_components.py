"""Shared, clearly labeled presentation for descriptive on/off samples."""

import math

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from rotation_lab.dashboard.impact import filter_sample, summarize, team_dataset
from rotation_lab.reporting.assets import player_headshot_url

METRICS = ["Margin / 48", "Team points / 48", "Opponent points / 48"]


def comparison_card(first, second, names):
    """Aligned values under player portraits; sample-aware gaps on the favorable side."""
    headers = []
    for result, name in zip([first, second], names, strict=True):
        headers.append(
            html.Div(
                [
                    html.Div(
                        html.Img(
                            src=player_headshot_url(result["player"]),
                            alt=name,
                            className="player-headshot-image",
                        ),
                        className="impact-portrait",
                    ),
                    html.H3(name),
                    html.P(sample_line(result), className="impact-note"),
                ],
                className="impact-contender",
            )
        )
    groups = []
    for mode, label in (("swing", "On/off change"), ("on", "While on court")):
        rows = []
        for index, metric in enumerate(METRICS):
            values = [
                r["swing"][index] if mode == "swing" else r["rates"][0][index]
                for r in (first, second)
            ]
            delta = values[0] - values[1]
            sufficient = (
                all(first["sufficient"] + second["sufficient"])
                if mode == "swing"
                else first["sufficient"][0] and second["sufficient"][0]
            )
            finite = math.isfinite(delta)
            leader = 0 if (delta > 0 if index != 2 else delta < 0) else 1
            ci = None
            if sufficient and first["draws"] is not None and second["draws"] is not None:
                draws = first["draws"][:, 0, index] - second["draws"][:, 0, index]
                if mode == "swing":
                    draws -= first["draws"][:, 1, index] - second["draws"][:, 1, index]
                if np.isfinite(draws).all():
                    ci = np.quantile(draws, [0.025, 0.975])
            uncertain = ci is None or ci[0] <= 0 <= ci[1]
            cells = []
            for side, value in enumerate(values):
                badge = None
                if sufficient and finite and abs(delta) >= 0.05 and side == leader:
                    badge = html.Span(
                        f"{abs(delta):.1f} {'lower' if index == 2 else 'higher'}",
                        className="impact-edge",
                    )
                cells.append(
                    html.Div(
                        [html.Strong(number(value, mode == "swing" or index == 0)), badge],
                        className="impact-value",
                    )
                )
            explanation = (
                "Not enough exposure"
                if not sufficient or not finite
                else "Essentially even"
                if abs(delta) < 0.05
                else "Observed gap · uncertain"
                if uncertain
                else "Observed gap"
            )
            detail = (
                f"Left − right · 95% interval: {ci[0]:+.1f} to {ci[1]:+.1f}"
                if ci is not None
                else "Intervals need 100 min and 10 games per relevant side."
            )
            rows.append(
                html.Div(
                    [
                        cells[0],
                        html.Div(
                            [
                                html.Div(metric, className="impact-metric-name"),
                                html.Small(
                                    "Lower is favorable" if index == 2 else "Higher is favorable"
                                ),
                                html.Div(explanation, className="impact-gap-note"),
                            ],
                            className="impact-metric",
                        ),
                        cells[1],
                        html.Div(detail, className="impact-gap-interval"),
                    ],
                    className="impact-match-row",
                )
            )
        groups.append(html.Div([html.H4(label), *rows], className="impact-match-group"))
    return html.Div(
        [
            html.Div(
                [headers[0], html.Div("VS", className="impact-versus"), headers[1]],
                className="impact-match-header",
            ),
            html.P(
                "Team outcomes per 48 minutes. Badges show the favorable observed difference, "
                "not a verdict on individual ability. Differences use unrounded rates.",
                className="impact-note",
            ),
            *groups,
        ],
        className="impact-match-card",
    )


def number(value, signed=False):
    return (f"{value:+.1f}" if signed else f"{value:.1f}") if math.isfinite(value) else "—"


def table(headers, rows):
    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([html.Th(label, scope="col") for label in headers])),
                html.Tbody([html.Tr([html.Td(value) for value in row]) for row in rows]),
            ],
            className="impact-table",
        ),
        className="impact-table-scroll",
        tabIndex=0,
    )


def interval_text(ci, metric=0):
    return f"{ci[0][metric]:+.1f} to {ci[1][metric]:+.1f}" if ci else "Not enough exposure"


def sample_line(result):
    return " · ".join(
        f"{label}: {result['totals'][side][0] / 60:,.1f} min / {result['games'][side]} games"
        for side, label in enumerate(("On", "Off"))
    )


def split_table(result):
    rows = []
    for index, metric in enumerate(METRICS):
        rows.append(
            [
                metric,
                number(result["rates"][0][index], index == 0),
                number(result["rates"][1][index], index == 0),
                number(result["swing"][index], True),
            ]
        )
    for label, index, divisor in [
        ("Minutes", 0, 60),
        ("Points for", 1, 1),
        ("Points against", 2, 1),
    ]:
        rows.append(
            [
                label,
                number(result["totals"][0][index] / divisor),
                number(result["totals"][1][index] / divisor),
                "—",
            ]
        )
    rows.append(["Games with exposure", *result["games"], "—"])
    rows.append(["Margin / 48 · 95% interval", *[interval_text(ci) for ci in result["ci"]]])
    return table(["Metric", "On court", "Off court", "On − off"], rows)


def margin_chart(result):
    figure = go.Figure()
    bounds = [0.0]
    for side, (name, color) in enumerate(
        (("On court", "#168577"), ("Off court", "#62758c"), ("Swing", "#2366b5"))
    ):
        value = result["rates"][side][0] if side < 2 else result["swing"][0]
        if not math.isfinite(value):
            continue
        ci = result["ci"][side]
        bounds.append(abs(value))
        # Draw bounds as a segment: percentile intervals need not contain the point estimate.
        if ci:
            bounds.extend([abs(ci[0][0]), abs(ci[1][0])])
            figure.add_trace(
                go.Scatter(
                    x=[ci[0][0], ci[1][0]],
                    y=[name, name],
                    mode="lines",
                    line=dict(color=color, width=5),
                    showlegend=False,
                    hovertemplate="95% interval: %{x:.1f}<extra></extra>",
                )
            )
        figure.add_trace(
            go.Scatter(
                x=[value],
                y=[name],
                mode="markers+text",
                text=[number(value, True)],
                textposition="top center",
                marker=dict(size=13, color=color),
                showlegend=False,
                hovertemplate=name + ": %{x:.1f} margin / 48<extra></extra>",
            )
        )
    figure.add_vline(x=0, line_color="#aeb8c4", line_dash="dot")
    figure.update_layout(
        height=275,
        margin=dict(l=80, r=25, t=35, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", color="#23344a"),
        xaxis=dict(
            title="Team margin per 48 minutes",
            zeroline=False,
            gridcolor="#e8edf2",
            range=[-max(5, max(bounds)) * 1.2, max(5, max(bounds)) * 1.2],
        ),
        yaxis=dict(
            categoryorder="array",
            categoryarray=["Swing", "Off court", "On court"],
            range=[-0.55, 2.6],
            fixedrange=True,
        ),
    )
    return dcc.Graph(
        figure=figure,
        style={"height": "275px", "minHeight": "275px", "width": "100%"},
        config={"displayModeBar": False, "responsive": True},
    )


def coverage_note(meta):
    return html.P(
        f"{meta['games']} of {meta['requested_games']} scoped games · "
        f"{meta['covered_minutes']:,.1f} covered team minutes · "
        f"{meta['coverage']:.1f}% of scoped game time · "
        f"{meta['excluded_games']} excluded games · "
        f"{meta['flagged_games']} included games with quality flags. "
        f"{meta['start'] or 'No dates'} → {meta['end'] or 'No dates'}.",
        className="impact-note",
    )


def game_impact(team, game_id):
    if not team or not game_id:
        return html.P("Select a game to see player on/off.")
    dataset = team_dataset(team)
    intervals, meta = filter_sample(dataset, [], universe="all", game_id=game_id)
    if intervals.empty:
        return html.P("On/off unavailable: this game has no fully validated scoring coverage.")
    rows = []
    for player in dataset["players"].itertuples():
        result = summarize(intervals, player.player_id, bootstrap=False)
        if result["totals"][0][0] <= 0:
            continue
        rows.append(
            [
                dcc.Link(
                    player.player_name, href=f"/player-impact?team={team}&player={player.player_id}"
                ),
                number(result["totals"][0][0] / 60),
                number(result["totals"][1][0] / 60),
                number(result["rates"][0][0], True),
                number(result["rates"][1][0], True),
                number(result["swing"][0], True),
            ]
        )
    return html.Div(
        [
            html.P(
                "What happened during playing and rest minutes in this game. "
                "These small samples describe the game; they do not rank player quality. "
                "A dash means no on- or off-court exposure.",
                className="impact-note",
            ),
            table(
                ["Player", "On min", "Off min", "On margin / 48", "Off margin / 48", "Swing / 48"],
                rows,
            ),
            coverage_note(meta),
        ]
    )
