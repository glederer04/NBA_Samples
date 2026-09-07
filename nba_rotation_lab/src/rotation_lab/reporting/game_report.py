"""Generate professional team game-review PDF reports."""

from __future__ import annotations

from datetime import date
from functools import partial
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from rotation_lab.reporting.branding import draw_report_frame
from rotation_lab.reporting.charts import margin_chart

NAVY = colors.HexColor("#111B2C")
BLUE = colors.HexColor("#2366D1")
ORANGE = colors.HexColor("#F27A2B")
LIGHT_BLUE = colors.HexColor("#EAF1FB")
LIGHT_GRAY = colors.HexColor("#F4F6F8")
MID_GRAY = colors.HexColor("#D9E0E8")
TEXT_GRAY = colors.HexColor("#53657D")
WHITE = colors.white


def generate_game_report(
    *,
    data: dict[str, Any],
    output_path: Path,
) -> Path:
    """Generate one team game-review PDF and return its path."""

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_game_report(
        data=data,
        destination=str(output_path),
    )

    return output_path


def generate_game_report_bytes(
    *,
    data: dict[str, Any],
) -> bytes:
    """Generate a game-review PDF entirely in memory."""

    buffer = BytesIO()

    _write_game_report(
        data=data,
        destination=buffer,
    )

    return buffer.getvalue()


def _write_game_report(
    *,
    data: dict[str, Any],
    destination: str | BytesIO,
) -> None:
    """Write the report to a path or in-memory buffer."""

    document = SimpleDocTemplate(
        destination,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.82 * inch,
        bottomMargin=0.65 * inch,
        title=(f"{data['team_abbreviation']} vs {data['opponent']} Game Review"),
        author="NBA Rotation Lab",
        subject="NBA rotation and lineup analysis",
    )

    styles = _build_styles()
    story = _build_story(
        data=data,
        styles=styles,
    )

    report_label = f"{data['team_abbreviation']} - {data['opponent']} | {data['game_id']}"
    page_callback = partial(
        _draw_header_footer,
        report_label=report_label,
        team_abbreviation=data["team_abbreviation"],
    )

    document.build(
        story,
        onFirstPage=page_callback,
        onLaterPages=page_callback,
    )


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the report's visual hierarchy."""

    sample_styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "RotationLabTitle",
            parent=sample_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "RotationLabSubtitle",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT_GRAY,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "RotationLabSection",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "RotationLabBody",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
        ),
        "metric": ParagraphStyle(
            "RotationLabMetric",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "small": ParagraphStyle(
            "RotationLabSmall",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=TEXT_GRAY,
        ),
        "table": ParagraphStyle(
            "RotationLabTable",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY,
        ),
        "table_header": ParagraphStyle(
            "RotationLabTableHeader",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
    }


def _build_story(
    *,
    data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the complete report flow."""

    location = "vs." if data["team_location"] == "home" else "at"
    game_date = _format_date(data["game_date"])
    validation = "Official score validated" if data["score_matches"] else "Score requires review"

    story: list[Any] = [
        Paragraph(
            "NBA ROTATION LAB",
            styles["small"],
        ),
        Paragraph(
            "Game Rotation Report",
            styles["title"],
        ),
        Paragraph(
            (
                f"{game_date} | {data['team_abbreviation']} "
                f"{location} {data['opponent']} | "
                f"Game ID {data['game_id']} | {validation}"
            ),
            styles["subtitle"],
        ),
        _score_table(data),
        Spacer(1, 12),
        _metric_table(data, styles),
        Spacer(1, 14),
        Paragraph(
            "Executive Readout",
            styles["section"],
        ),
        *_executive_readout(data, styles),
        Spacer(1, 7),
        Paragraph(
            "Period Performance",
            styles["section"],
        ),
        margin_chart(
            [_period_label(int(row[0])) for row in data["periods"]],
            [float(row[3]) for row in data["periods"]],
        ),
        Spacer(1, 10),
        _period_table(data["periods"], styles),
        PageBreak(),
        Spacer(1, 22),
        Paragraph(
            "Rotation Detail",
            styles["title"],
        ),
        Paragraph(
            ("Lineup performance and rotation stretches for staff review."),
            styles["subtitle"],
        ),
        Paragraph(
            "Most-Used Lineups",
            styles["section"],
        ),
        _lineup_table(data["lineups"], styles),
        Spacer(1, 12),
        Paragraph(
            "Rotation Stretches",
            styles["section"],
        ),
        _stretch_table(data["stretches"], styles),
        Spacer(1, 12),
        Paragraph(
            "Methodology Note",
            styles["section"],
        ),
        Paragraph(
            (
                "Rotation intervals are reconstructed from NBA "
                "rotation and play-by-play data. Points occurring "
                "at an exact substitution timestamp use an "
                "end-inclusive assignment convention. "
                f"{data['boundary_scoring_points']} points in this "
                "game occurred on a lineup-change boundary."
            ),
            styles["body"],
        ),
    ]

    return story


def _score_table(data: dict[str, Any]) -> Table:
    """Create the primary game result treatment."""

    score = f"{data['points_for']}  -  {data['points_against']}"

    table = Table(
        [
            [
                data["team_abbreviation"],
                score,
                data["opponent"],
            ],
            [
                "TEAM",
                f"{data['result']} | {_signed(data['plus_minus'])}",
                "OPPONENT",
            ],
        ],
        colWidths=[
            1.4 * inch,
            4.2 * inch,
            1.4 * inch,
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 17),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, 1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
                ("BOX", (0, 0), (-1, -1), 0.75, NAVY),
                ("LINEBEFORE", (1, 0), (1, -1), 0.5, TEXT_GRAY),
                ("LINEAFTER", (1, 0), (1, -1), 0.5, TEXT_GRAY),
            ]
        )
    )

    return table


def _metric_table(
    data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the game-level rotation KPI row."""

    metrics = [
        ("LINEUPS", data["lineups_used"]),
        ("CHANGES", data["lineup_changes"]),
        ("INTERVALS", data["rotation_intervals"]),
        (
            "BEST PERIOD",
            f"{_period_label(data['best_period'])} {_signed(data['best_period_plus_minus'])}",
        ),
        (
            "WORST PERIOD",
            f"{_period_label(data['worst_period'])} {_signed(data['worst_period_plus_minus'])}",
        ),
    ]

    cells = [
        Paragraph(
            f"<b>{escape(str(value))}</b><br/><font color='#53657D'>{label}</font>",
            styles["metric"],
        )
        for label, value in metrics
    ]

    table = Table(
        [cells],
        colWidths=[1.4 * inch] * 5,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, MID_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    return table


def _executive_readout(
    data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Paragraph]:
    """Create deterministic coach-facing observations."""

    observations = [
        (
            f"<b>1.</b> {data['team_abbreviation']} finished "
            f"{_signed(data['plus_minus'])} in a "
            f"{data['points_for']}-{data['points_against']} "
            f"{data['result']}."
        ),
        (
            f"<b>2.</b> The staff used {data['lineups_used']} "
            f"lineups across {data['rotation_intervals']} "
            f"rotation intervals and made "
            f"{data['lineup_changes']} lineup changes."
        ),
        (
            f"<b>3.</b> {_period_label(data['best_period'])} "
            f"was the strongest segment "
            f"({_signed(data['best_period_plus_minus'])}); "
            f"{_period_label(data['worst_period'])} was the "
            f"weakest ({_signed(data['worst_period_plus_minus'])})."
        ),
    ]

    return [
        Paragraph(
            observation,
            styles["body"],
        )
        for observation in observations
    ]


def _period_table(
    periods: list[tuple],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the period performance table."""

    rows: list[list[Any]] = [
        _header_row(
            [
                "PERIOD",
                "POINTS FOR",
                "POINTS AGAINST",
                "+/-",
                "LINEUPS",
                "INTERVALS",
            ],
            styles,
        )
    ]

    for period in periods:
        rows.append(
            [
                _period_label(int(period[0])),
                int(period[1]),
                int(period[2]),
                _signed(int(period[3])),
                int(period[4]),
                int(period[5]),
            ]
        )

    return _styled_table(
        rows,
        col_widths=[
            0.8 * inch,
            1.05 * inch,
            1.2 * inch,
            0.75 * inch,
            1.0 * inch,
            1.0 * inch,
        ],
    )


def _lineup_table(
    lineups: list[tuple],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the most-used lineup table."""

    rows: list[list[Any]] = [
        _header_row(
            [
                "LINEUP",
                "MIN",
                "PF",
                "PA",
                "+/-",
                "+/- PER 48",
            ],
            styles,
        )
    ]

    for lineup in lineups:
        lineup_names = escape(str(lineup[1])).replace(
            " | ",
            ", ",
        )
        rows.append(
            [
                Paragraph(
                    lineup_names,
                    styles["table"],
                ),
                f"{float(lineup[2]):.1f}",
                int(lineup[3]),
                int(lineup[4]),
                _signed(int(lineup[5])),
                _signed(float(lineup[6])),
            ]
        )

    return _styled_table(
        rows,
        col_widths=[
            3.1 * inch,
            0.55 * inch,
            0.45 * inch,
            0.45 * inch,
            0.55 * inch,
            0.8 * inch,
        ],
    )


def _stretch_table(
    stretches: list[tuple],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the longest rotation-stretch table."""

    rows: list[list[Any]] = [
        _header_row(
            [
                "PERIOD",
                "CLOCK",
                "LINEUP",
                "MIN",
                "+/-",
                "BOUNDARY PTS",
            ],
            styles,
        )
    ]

    for stretch in stretches:
        period = int(stretch[0])
        lineup_names = escape(str(stretch[4])).replace(
            " | ",
            ", ",
        )
        clock_range = f"{_clock(period, int(stretch[1]))} - {_clock(period, int(stretch[2]))}"

        rows.append(
            [
                _period_label(period),
                clock_range,
                Paragraph(
                    lineup_names,
                    styles["table"],
                ),
                f"{float(stretch[3]) / 60:.1f}",
                _signed(int(stretch[7])),
                int(stretch[8]),
            ]
        )

    return _styled_table(
        rows,
        col_widths=[
            0.55 * inch,
            1.15 * inch,
            3.15 * inch,
            0.55 * inch,
            0.55 * inch,
            0.8 * inch,
        ],
    )


def _header_row(
    labels: list[str],
    styles: dict[str, ParagraphStyle],
) -> list[Paragraph]:
    """Create one formatted table header row."""

    return [
        Paragraph(
            label,
            styles["table_header"],
        )
        for label in labels
    ]


def _styled_table(
    rows: list[list[Any]],
    *,
    col_widths: list[float],
) -> Table:
    """Apply the shared analytical-table treatment."""

    table = Table(
        rows,
        colWidths=[column / sum(col_widths) * 7 * inch for column in col_widths],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("GRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    return table


def _draw_header_footer(
    pdf_canvas: Canvas,
    document: SimpleDocTemplate,
    *,
    report_label: str,
    team_abbreviation: str = "",
) -> None:
    """Draw the common branded report frame."""
    draw_report_frame(
        pdf_canvas, document, report_label=report_label, team_abbreviation=team_abbreviation
    )


def _format_date(value: object) -> str:
    """Return a human-readable game date."""

    if isinstance(value, date):
        return value.strftime("%B %d, %Y")

    return str(value)


def _period_label(period: int) -> str:
    """Return a regulation or overtime label."""

    if period <= 4:
        return f"Q{period}"

    return f"OT{period - 4}"


def _clock(
    period: int,
    elapsed_deciseconds: int,
) -> str:
    """Convert game elapsed time to a period clock."""

    if period <= 4:
        period_start = (period - 1) * 7200
        period_length = 7200
    else:
        period_start = 28800 + (period - 5) * 3000
        period_length = 3000

    elapsed_in_period = max(
        0,
        elapsed_deciseconds - period_start,
    )
    remaining = max(
        0,
        period_length - elapsed_in_period,
    )

    minutes = remaining // 600
    seconds = (remaining % 600) // 10

    return f"{minutes}:{seconds:02d}"


def _signed(value: int | float) -> str:
    """Format a signed analytical value."""

    numeric_value = float(value)

    if numeric_value.is_integer():
        return f"{int(numeric_value):+d}"

    return f"{numeric_value:+.1f}"


def _clip_text(
    value: str,
    max_width: float,
    font_name: str,
    font_size: float,
) -> str:
    """Clip a header label to the available width."""

    if (
        stringWidth(
            value,
            font_name,
            font_size,
        )
        <= max_width
    ):
        return value

    clipped = value

    while (
        clipped
        and stringWidth(
            f"{clipped}...",
            font_name,
            font_size,
        )
        > max_width
    ):
        clipped = clipped[:-1]

    return f"{clipped}..."
