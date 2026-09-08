"""Shared offline branding for both report types."""

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

from rotation_lab.config import ASSETS_DIR


def draw_report_frame(canvas, document, *, report_label: str, team_abbreviation: str) -> None:
    """Draw restrained team branding, report context, and consistent pagination."""

    canvas.saveState()
    width, height = document.pagesize
    left, right = document.leftMargin, width - document.rightMargin
    canvas.setFillColor(colors.HexColor("#111B2C"))
    canvas.rect(0, height - 10, width, 10, fill=1, stroke=0)
    logo = ASSETS_DIR / "team-logos" / "normalized" / f"{team_abbreviation.upper()}.png"
    text_left = left
    if logo.is_file():
        canvas.drawImage(
            ImageReader(str(logo)),
            left,
            height - 39,
            25,
            25,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        text_left += 34
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(text_left, height - 30, "NBA ROTATION LAB")
    available = right - text_left - stringWidth("NBA ROTATION LAB", "Helvetica-Bold", 8) - 20
    label = report_label
    while label and stringWidth(label, "Helvetica", 7) > available:
        label = label[:-1]
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#53657D"))
    canvas.drawRightString(right, height - 30, label)
    canvas.setStrokeColor(colors.HexColor("#D9E0E8"))
    canvas.setLineWidth(0.5)
    canvas.line(left, height - 43, right, height - 43)
    canvas.line(left, 35, right, 35)
    canvas.drawString(left, 22, "Decision-support analysis | NBA Rotation Lab")
    canvas.drawRightString(right, 22, f"Page {document.page}")
    canvas.restoreState()
