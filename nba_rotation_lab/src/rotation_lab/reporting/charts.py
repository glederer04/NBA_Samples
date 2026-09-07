"""Small vector report charts using already-computed basketball metrics."""

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor


def margin_chart(labels: list[str], values: list[float], *, width: float = 504) -> Drawing:
    """Render signed margins without introducing analytical calculations."""

    drawing = Drawing(width, 125)
    if not values:
        return drawing
    bound = max(max(abs(value) for value in values), 1)
    baseline = 63
    slot = width / len(values)
    drawing.add(Line(0, baseline, width, baseline, strokeColor=HexColor("#9AA6B5")))
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        center = slot * (index + 0.5)
        bar_height = abs(value) / bound * 35
        bottom = baseline if value >= 0 else baseline - bar_height
        drawing.add(
            Rect(
                center - slot * 0.22,
                bottom,
                slot * 0.44,
                bar_height,
                fillColor=HexColor("#16855B" if value >= 0 else "#C5424D"),
                strokeColor=None,
            )
        )
        drawing.add(
            String(
                center,
                baseline + bar_height + 6 if value >= 0 else bottom - 12,
                f"{value:+g}",
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=8,
                fillColor=HexColor("#182235"),
            )
        )
        drawing.add(
            String(
                center,
                1,
                label,
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=8,
                fillColor=HexColor("#53657D"),
            )
        )
    return drawing
