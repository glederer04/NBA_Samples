"""Exact-snapshot coaching PDF. Rendering never queries data or reruns the solver."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from rotation_lab.modeling.planner_plan import validate_snapshot

NAVY = colors.HexColor("#17243a")
BLUE = colors.HexColor("#2563eb")
PALETTE = [
    "#2563eb",
    "#0891b2",
    "#7c3aed",
    "#d97706",
    "#059669",
    "#db2777",
    "#475569",
    "#9333ea",
    "#0e7490",
    "#a16207",
    "#be123c",
    "#4338ca",
]


def generate_player_plan_report_bytes(plan):
    errors = validate_snapshot(plan)
    if errors:
        raise ValueError(" ".join(errors))
    output = BytesIO()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "PlanBody", fontName="Helvetica", fontSize=8.5, leading=12, textColor=NAVY, spaceAfter=7
    )
    small = ParagraphStyle("PlanSmall", parent=normal, fontSize=7.3, leading=10, spaceAfter=0)
    heading = ParagraphStyle(
        "PlanHeading",
        parent=styles["Heading2"],
        textColor=NAVY,
        fontSize=13,
        spaceBefore=12,
        spaceAfter=8,
    )

    def p(text, style=normal):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def grid(headers, rows, widths):
        t = Table(
            [[p(x, small) for x in headers]] + [[p(x, small) for x in row] for row in rows],
            colWidths=widths,
            repeatRows=1,
            hAlign="LEFT",
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dfe6ef")),
                ]
            )
        )
        return t

    people = {r["id"]: r["name"] for r in plan["players"]}

    def names(key):
        return " / ".join(people[pid] for pid in key.split("-"))

    def frame(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#dfe6ef"))
        canvas.line(36, 752, 576, 752)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(BLUE)
        canvas.drawString(36, 764, "NBA ROTATION LAB")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(NAVY)
        canvas.drawRightString(576, 764, plan["request"]["team"] + " | PLAYER-MINUTE PLAN")
        canvas.drawString(36, 22, f"Saved {plan['created'][:19]} UTC | {plan['id']}")
        canvas.drawRightString(576, 22, f"Page {doc.page}")

    story = [
        p(
            "Coaching schedule",
            ParagraphStyle(
                "Title",
                parent=styles["Title"],
                alignment=TA_LEFT,
                textColor=NAVY,
                fontSize=23,
                spaceAfter=10,
            ),
        ),
        p(
            f"{plan['request']['team']} | 48 minutes | 240 player-minutes | "
            f"{plan['solver']['status'].title()} | {plan['substitutions']} player "
            f"entries after tip-off"
        ),
        p(
            f"Historical estimate: {plan['mu']:+.1f} margin / 48. 95% estimate range: "
            f"{plan['interval'][0]:+.1f} to {plan['interval'][1]:+.1f}. Established "
            f"lineup share: {plan['established']:.0f}%. This is not a final-score "
            f"forecast."
        ),
    ]
    height = 38 + len(plan["players"]) * 16
    drawing = Drawing(540, height)
    left = 130
    scale = 400 / 48
    for q in range(5):
        x = left + q * 12 * scale
        drawing.add(
            Line(x, 20, x, height - 8, strokeColor=colors.HexColor("#dfe6ef"), strokeWidth=0.6)
        )
        drawing.add(String(x, 5, str(q * 12), fontName="Helvetica", fontSize=7, fillColor=NAVY))
    for i, person in enumerate(plan["players"]):
        y = height - 24 - i * 16
        drawing.add(
            String(0, y + 3, person["name"], fontName="Helvetica", fontSize=8, fillColor=NAVY)
        )
        for a, b in person["stints"]:
            drawing.add(
                Rect(
                    left + a * scale,
                    y,
                    (b - a) * scale,
                    10,
                    fillColor=colors.HexColor(PALETTE[i]),
                    strokeColor=None,
                )
            )
    story.extend(
        [
            drawing,
            p(
                (
                    "Elapsed game minutes. Each player retains one color. Full five-player "
                    "stint schedule follows."
                ),
                small,
            ),
            Spacer(1, 8),
            grid(
                ["Player", "Min / target / max", "Assigned", "Max stint / rest", "Open / close"],
                [
                    [
                        r["name"],
                        f"{r['min']} / {r['target']} / {r['max']}",
                        r["assigned"],
                        f"{r['stint']} / {r['rest']}",
                        ("Yes" if r.get("starter") else "-")
                        + " / "
                        + ("Yes" if r.get("closer") else "-"),
                    ]
                    for r in plan["players"]
                ],
                [150, 110, 65, 110, 105],
            ),
            Spacer(1, 10),
            p(
                (
                    "All hard constraints passed independent validation. One-minute grid; "
                    "regulation only. Quarter breaks reset stint length and credit 2 / 15 / 2 "
                    "minutes of rest. Substitutions still depend on stoppages."
                ),
                small,
            ),
            PageBreak(),
            p("Who shares the floor", heading),
            grid(
                ["Quarter / elapsed minutes", "Five-player unit"],
                [
                    [f"Q{s['start'] // 12 + 1} | {s['start']}-{s['end']}", names(s["key"])]
                    for s in plan["segments"]
                ],
                [110, 430],
            ),
            PageBreak(),
            p("Lineup evidence", heading),
            grid(
                ["Five-player unit", "Planned min", "Direct min / games", "Est. / 48", "95% range"],
                [
                    [
                        names(u["key"]),
                        plan["schedule"].count(u["key"]),
                        (
                            f"{'<1' if 0 < u['minutes'] < 1 else format(u['minutes'], '.0f')} "
                            f"/ {u['games']}"
                        ),
                        f"{u['mu']:+.1f}",
                        f"{u['interval'][0]:+.1f} to {u['interval'][1]:+.1f}",
                    ]
                    for u in plan["units"]
                ],
                [240, 55, 90, 65, 90],
            ),
            p(
                "Observed units blend direct scoring with 48 prior minutes. Unobserved "
                "units have no direct sample. Established means at least 100 minutes and "
                "10 games. Whole-game bootstrap refits (200) preserve covariance across "
                "units; the range describes estimation uncertainty, not future game "
                "variability. No overlapping trio or raw individual on/off rates are "
                "added together."
            ),
            p("Constraints & assumptions", heading),
        ]
    )
    r = plan["request"]
    story.append(
        p(
            f"Priority: {r['preset']}. Opponent: {r.get(('opponent'), ('average'))}; "
            f"venue: {r.get(('venue'), ('neutral'))}. Unobserved candidates: "
            f"{('allowed') if r.get('unseen') else ('excluded')}."
        )
    )
    for role in r.get("roles", []):
        story.append(
            p(
                f"Always include {role}: "
                + ", ".join(person["name"] for person in r["players"] if person.get(role))
            )
        )
    for pair in plan["pairs"]:
        story.append(
            p(
                f"{pair['kind'].title()}: "
                + " + ".join(people[i] for i in pair["players"])
                + f". Shared minutes: {pair['together']}."
            )
        )
    for w in r.get("windows", []):
        story.append(p(f"Rest: {people[w['player']]} at minutes {w['start']}-{w['end']}."))
    for lock in r.get("locks", []):
        story.append(p(f"Locked minutes {lock['start']}-{lock['end']}: {names(lock['key'])}."))
    a = plan["audit"]
    if a.get("available"):
        story.append(
            p(
                (
                    f"Chronological audit: {a['train_games']} train, {a['tune_games']} tune, "
                    f"{a['test_games']} later test games. Weighted interval RMSE: context "
                    f"blend {a['blended_error']:.2f}, team baseline "
                    f"{a['baseline_error']:.2f}, existing lineup shrinkage "
                    f"{a['lineup_error']:.2f}. "
                )
                + (
                    "Context blend enabled."
                    if a["use_context"]
                    else (
                        "Context blend failed to beat both baselines; historical team-prior "
                        "shrinkage used. Opponent and venue do not change these estimates."
                    )
                )
            )
        )
    story.extend(
        [
            p(
                "Context uses player presence, opponent identity, home court, period and "
                "prior score state; full opponent lineups are unavailable. Planning "
                "assumes neutral score state and equal quarter weights. Roles are "
                "coach-defined. No injury, learned fatigue, causal impact or "
                "possession-based forecasts are claimed."
            ),
            p(
                (
                    f"Data: {plan['data_start']} to {plan['data_end']}; season "
                    f"{plan['season']}. Dataset {plan['dataset']}; model "
                    f"{plan['model_version']}; planner {plan['version']}. Solver "
                    f"{plan['solver']['seconds']:.1f}s; gap {plan['solver'].get('gap')}. "
                    f"{plan['solver']['messages'][0]}"
                ),
                small,
            ),
        ]
    )
    comparison = plan.get("comparison")
    if comparison:
        story.extend(
            [
                p("Comparison with previous saved plan", heading),
                p(
                    f"Previous plan {comparison['id']} saved {comparison['created'][:19]} UTC. "
                    f"{comparison['changed_minutes']} of 48 lineup minutes changed. "
                    + (
                        "Same constraints."
                        if comparison["same_constraints"]
                        else "Different inputs; this includes minute or availability changes."
                    )
                ),
                grid(
                    ["Metric", "Previous plan", "This plan", "Change"],
                    [
                        [
                            "Estimated margin / 48",
                            f"{comparison['mu']:+.1f}",
                            f"{plan['mu']:+.1f}",
                            f"{plan['mu'] - comparison['mu']:+.1f}",
                        ],
                        [
                            "Established share",
                            f"{comparison['established']:.0f}%",
                            f"{plan['established']:.0f}%",
                            f"{plan['established'] - comparison['established']:+.0f} pp",
                        ],
                        [
                            "Player entries",
                            comparison["substitutions"],
                            plan["substitutions"],
                            plan["substitutions"] - comparison["substitutions"],
                        ],
                    ],
                    [180, 120, 120, 120],
                ),
            ]
        )
    SimpleDocTemplate(
        output,
        pagesize=(612, 792),
        leftMargin=36,
        rightMargin=36,
        topMargin=52,
        bottomMargin=38,
        title=f"{r['team']} Player-minute plan",
        author="NBA Rotation Lab",
    ).build(story, onFirstPage=frame, onLaterPages=frame)
    return output.getvalue()
