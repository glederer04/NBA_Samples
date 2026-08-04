"""Generate professional rotation-scenario PDF reports."""

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
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from rotation_lab.modeling import (
    LineupAllocation,
    RotationPlanProjection,
    describe_rotation_plan,
)

NAVY = colors.HexColor("#111B2C")
BLUE = colors.HexColor("#2366D1")
GREEN = colors.HexColor("#16855B")
RED = colors.HexColor("#C5424D")
ORANGE = colors.HexColor("#F27A2B")
LIGHT_BLUE = colors.HexColor("#EAF1FB")
LIGHT_GRAY = colors.HexColor("#F4F6F8")
MID_GRAY = colors.HexColor("#D9E0E8")
TEXT_GRAY = colors.HexColor("#53657D")
WHITE = colors.white


def generate_scenario_report(
    *,
    allocations: list[LineupAllocation],
    projection: RotationPlanProjection,
    output_path: Path,
) -> Path:
    """Generate a rotation-scenario PDF and return its path."""

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_scenario_report(
        allocations=allocations,
        projection=projection,
        destination=str(output_path),
    )

    return output_path


def generate_scenario_report_bytes(
    *,
    allocations: list[LineupAllocation],
    projection: RotationPlanProjection,
) -> bytes:
    """Generate a rotation-scenario PDF entirely in memory."""

    buffer = BytesIO()

    _write_scenario_report(
        allocations=allocations,
        projection=projection,
        destination=buffer,
    )

    return buffer.getvalue()


def _write_scenario_report(
    *,
    allocations: list[LineupAllocation],
    projection: RotationPlanProjection,
    destination: str | BytesIO,
) -> None:
    """Write the complete scenario report."""

    if not allocations:
        raise ValueError("allocations cannot be empty")

    document = SimpleDocTemplate(
        destination,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.82 * inch,
        bottomMargin=0.65 * inch,
        title=f"{projection.team_abbreviation} Rotation Scenario Report",
        author="NBA Rotation Lab",
        subject="NBA lineup allocation and rotation planning analysis",
    )

    styles = _build_styles()
    story = _build_story(
        allocations=allocations,
        projection=projection,
        styles=styles,
    )

    page_callback = partial(
        _draw_header_footer,
        report_label=f"{projection.team_abbreviation} Rotation Scenario",
    )

    document.build(
        story,
        onFirstPage=page_callback,
        onLaterPages=page_callback,
    )


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the report visual hierarchy."""

    sample_styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ScenarioReportTitle",
            parent=sample_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "ScenarioReportSubtitle",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT_GRAY,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "ScenarioReportSection",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "ScenarioReportBody",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=NAVY,
        ),
        "metric": ParagraphStyle(
            "ScenarioReportMetric",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "ScenarioReportMetricLabel",
            parent=sample_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=8,
            textColor=TEXT_GRAY,
            alignment=TA_CENTER,
        ),
        "small": ParagraphStyle(
            "ScenarioReportSmall",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=TEXT_GRAY,
        ),
        "table": ParagraphStyle(
            "ScenarioReportTable",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY,
        ),
        "table_header": ParagraphStyle(
            "ScenarioReportTableHeader",
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
    allocations: list[LineupAllocation],
    projection: RotationPlanProjection,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the complete report flow."""

    generated_date = date.today().strftime("%B %d, %Y")

    story: list[Any] = [
        Paragraph(
            "NBA ROTATION LAB",
            styles["small"],
        ),
        Paragraph(
            "Rotation Scenario Report",
            styles["title"],
        ),
        Paragraph(
            (
                f"{escape(projection.team_abbreviation)} | "
                f"Generated {generated_date} | "
                f"{len(allocations)} selected five-player units"
            ),
            styles["subtitle"],
        ),
        _metric_table(
            projection=projection,
            styles=styles,
        ),
        Spacer(1, 14),
        Paragraph(
            "Staff Readout",
            styles["section"],
        ),
        Paragraph(
            describe_rotation_plan(projection),
            styles["body"],
        ),
        Spacer(1, 12),
        Paragraph(
            "Planned Allocation Summary",
            styles["section"],
        ),
        _allocation_table(
            allocations=allocations,
            styles=styles,
        ),
        Spacer(1, 12),
        Paragraph(
            "Decision Context",
            styles["section"],
        ),
        Paragraph(
            _decision_context(projection),
            styles["body"],
        ),
        PageBreak(),
        Spacer(1, 22),
        Paragraph(
            "Lineup Allocation Detail",
            styles["title"],
        ),
        Paragraph(
            ("Unit-level performance, sample information, confidence, and planning designation."),
            styles["subtitle"],
        ),
        _lineup_detail_table(
            allocations=allocations,
            styles=styles,
        ),
        Spacer(1, 14),
        Paragraph(
            "Interpretation Guide",
            styles["section"],
        ),
        _interpretation_table(styles),
        Spacer(1, 14),
        Paragraph(
            "Methodology and Use",
            styles["section"],
        ),
        Paragraph(
            (
                "Scenario estimates weight each selected lineup's adjusted "
                "plus-minus per 48 by its planned minutes. The scenario is "
                "then compared with the team's observed lineup baseline. "
                "Confidence is also minutes-weighted and reflects the sample "
                "strength supporting the selected units."
            ),
            styles["body"],
        ),
        Spacer(1, 7),
        Paragraph(
            (
                "This report is a decision-support artifact. It helps staff "
                "compare possible rotation allocations, identify units that "
                "deserve additional consideration, and communicate the "
                "evidence behind a plan. It is not a causal forecast and does "
                "not account for opponent matchups, injuries, foul trouble, "
                "game state, or unobserved lineup interactions."
            ),
            styles["body"],
        ),
    ]

    return story


def _metric_table(
    *,
    projection: RotationPlanProjection,
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the executive summary metric row."""

    metrics = [
        (
            "PLANNED MINUTES",
            f"{projection.total_planned_minutes:.1f}",
        ),
        (
            "SCENARIO +/- 48",
            _format_signed(projection.weighted_adjusted_plus_minus_per_48),
        ),
        (
            "TEAM BASELINE",
            _format_signed(projection.team_plus_minus_per_48),
        ),
        (
            "DIFFERENCE",
            _format_signed(projection.projected_difference_per_48),
        ),
        (
            "CONFIDENCE",
            f"{projection.weighted_confidence_percentage:.1f}%",
        ),
    ]

    data = [
        [Paragraph(label, styles["metric_label"]) for label, _value in metrics],
        [Paragraph(value, styles["metric"]) for _label, value in metrics],
    ]

    table = Table(
        data,
        colWidths=[1.38 * inch] * 5,
        rowHeights=[
            0.28 * inch,
            0.48 * inch,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT_GRAY,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    MID_GRAY,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    MID_GRAY,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def _allocation_table(
    *,
    allocations: list[LineupAllocation],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the first-page lineup allocation table."""

    rows: list[list[Any]] = [
        [
            Paragraph("RANK", styles["table_header"]),
            Paragraph("FIVE-PLAYER UNIT", styles["table_header"]),
            Paragraph("MINUTES", styles["table_header"]),
            Paragraph("ADJ +/- 48", styles["table_header"]),
            Paragraph("CONFIDENCE", styles["table_header"]),
        ]
    ]

    for allocation in allocations:
        recommendation = allocation.recommendation

        rows.append(
            [
                str(recommendation.recommendation_rank),
                Paragraph(
                    escape(" | ".join(recommendation.player_names)),
                    styles["table"],
                ),
                f"{allocation.planned_minutes:.1f}",
                _format_signed(recommendation.adjusted_plus_minus_per_48),
                f"{recommendation.confidence_percentage:.1f}%",
            ]
        )

    table = Table(
        rows,
        colWidths=[
            0.48 * inch,
            3.75 * inch,
            0.72 * inch,
            0.92 * inch,
            0.98 * inch,
        ],
        repeatRows=1,
    )

    table.setStyle(_standard_table_style())

    return table


def _lineup_detail_table(
    *,
    allocations: list[LineupAllocation],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the second-page lineup detail table."""

    rows: list[list[Any]] = [
        [
            Paragraph("FIVE-PLAYER UNIT", styles["table_header"]),
            Paragraph("PLAN", styles["table_header"]),
            Paragraph("SAMPLE", styles["table_header"]),
            Paragraph("PERFORMANCE", styles["table_header"]),
            Paragraph("STATUS", styles["table_header"]),
        ]
    ]

    for allocation in allocations:
        recommendation = allocation.recommendation

        sample_text = (
            f"{recommendation.games_used} games<br/>"
            f"{recommendation.total_minutes:.1f} observed min<br/>"
            f"Through {recommendation.latest_game_date:%b %d, %Y}"
        )
        performance_text = (
            f"Raw: {_format_signed(recommendation.raw_plus_minus_per_48)}<br/>"
            f"Adjusted: "
            f"{_format_signed(recommendation.adjusted_plus_minus_per_48)}<br/>"
            f"Baseline: {_format_signed(recommendation.team_plus_minus_per_48)}"
        )
        status_text = (
            f"{escape(recommendation.recommendation.title())}<br/>"
            f"{escape(recommendation.sample_size_status.title())}<br/>"
            f"{recommendation.confidence_percentage:.1f}% confidence"
        )

        rows.append(
            [
                Paragraph(
                    escape(" | ".join(recommendation.player_names)),
                    styles["table"],
                ),
                Paragraph(
                    f"<b>{allocation.planned_minutes:.1f} min</b>",
                    styles["table"],
                ),
                Paragraph(
                    sample_text,
                    styles["table"],
                ),
                Paragraph(
                    performance_text,
                    styles["table"],
                ),
                Paragraph(
                    status_text,
                    styles["table"],
                ),
            ]
        )

    table = Table(
        rows,
        colWidths=[
            2.65 * inch,
            0.68 * inch,
            1.32 * inch,
            1.25 * inch,
            1.05 * inch,
        ],
        repeatRows=1,
    )

    table.setStyle(_standard_table_style())

    return table


def _interpretation_table(
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Create the assessment interpretation guide."""

    rows = [
        [
            Paragraph("ASSESSMENT", styles["table_header"]),
            Paragraph("RULE", styles["table_header"]),
            Paragraph("STAFF INTERPRETATION", styles["table_header"]),
        ],
        [
            Paragraph("<b>Positive</b>", styles["table"]),
            Paragraph("At least +3.0 points per 48", styles["table"]),
            Paragraph(
                "The plan grades meaningfully above the current team baseline.",
                styles["table"],
            ),
        ],
        [
            Paragraph("<b>Neutral</b>", styles["table"]),
            Paragraph("Between -3.0 and +3.0", styles["table"]),
            Paragraph(
                "The plan grades near the current team baseline.",
                styles["table"],
            ),
        ],
        [
            Paragraph("<b>Negative</b>", styles["table"]),
            Paragraph("At most -3.0 points per 48", styles["table"]),
            Paragraph(
                "The plan grades meaningfully below the current team baseline.",
                styles["table"],
            ),
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            1.05 * inch,
            2.15 * inch,
            3.65 * inch,
        ],
        repeatRows=1,
    )

    table.setStyle(_standard_table_style())

    return table


def _standard_table_style() -> TableStyle:
    """Return the shared report table styling."""

    return TableStyle(
        [
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                NAVY,
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                WHITE,
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                WHITE,
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    WHITE,
                    LIGHT_GRAY,
                ],
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                MID_GRAY,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.35,
                MID_GRAY,
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, 0),
                "CENTER",
            ),
            (
                "ALIGN",
                (0, 1),
                (0, -1),
                "CENTER",
            ),
            (
                "ALIGN",
                (2, 1),
                (-1, -1),
                "CENTER",
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ]
    )


def _decision_context(
    projection: RotationPlanProjection,
) -> str:
    """Create an assessment-specific staff note."""

    if projection.assessment == "positive":
        return (
            "The selected allocation is a candidate for increased use or "
            "targeted matchup testing. Staff should still review opponent "
            "personnel, lineup role balance, and the source of the observed edge."
        )

    if projection.assessment == "negative":
        return (
            "The selected allocation grades below the current baseline. Staff "
            "may want to reduce the proposed minutes, replace a unit, or identify "
            "whether the lineup serves a situational purpose not captured here."
        )

    return (
        "The selected allocation grades close to the current baseline. The "
        "decision may depend more heavily on matchup fit, player availability, "
        "role continuity, and the value of maintaining a stable rotation."
    )


def _format_signed(value: float) -> str:
    """Format a value with an explicit sign."""

    return f"{value:+.1f}"


def _draw_header_footer(
    canvas: Canvas,
    document: SimpleDocTemplate,
    *,
    report_label: str,
) -> None:
    """Draw consistent report framing and page numbers."""

    canvas.saveState()

    page_width, page_height = letter

    canvas.setFillColor(NAVY)
    canvas.rect(
        0,
        page_height - 0.18 * inch,
        page_width,
        0.18 * inch,
        fill=1,
        stroke=0,
    )

    canvas.setStrokeColor(MID_GRAY)
    canvas.setLineWidth(0.6)
    canvas.line(
        0.65 * inch,
        0.48 * inch,
        page_width - 0.65 * inch,
        0.48 * inch,
    )

    canvas.setFont(
        "Helvetica",
        7,
    )
    canvas.setFillColor(TEXT_GRAY)
    canvas.drawString(
        0.65 * inch,
        0.3 * inch,
        report_label,
    )
    canvas.drawRightString(
        page_width - 0.65 * inch,
        0.3 * inch,
        f"NBA Rotation Lab | Page {document.page}",
    )

    canvas.restoreState()
