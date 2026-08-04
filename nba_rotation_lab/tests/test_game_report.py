"""Tests for professional PDF game reports."""

from datetime import date
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from rotation_lab.reporting import (
    generate_game_report,
    generate_game_report_bytes,
)


def test_generate_game_report_creates_readable_pdf(
    tmp_path: Path,
) -> None:
    """A generated report should contain key decision-support text."""

    output_path = tmp_path / "game_report.pdf"

    data = {
        "game_id": "0022500153",
        "game_date": date(2025, 11, 2),
        "team_abbreviation": "NYK",
        "opponent": "CHI",
        "team_location": "home",
        "result": "W",
        "points_for": 128,
        "points_against": 116,
        "plus_minus": 12,
        "rotation_intervals": 27,
        "lineups_used": 22,
        "lineup_changes": 26,
        "boundary_scoring_points": 4,
        "best_period": 4,
        "best_period_plus_minus": 9,
        "worst_period": 2,
        "worst_period_plus_minus": -4,
        "score_matches": True,
        "periods": [
            (1, 31, 28, 3, 7, 8),
            (2, 27, 31, -4, 8, 7),
            (3, 33, 32, 1, 7, 6),
            (4, 37, 25, 12, 6, 6),
        ],
        "lineups": [
            (
                "1-2-3-4-5",
                "Player One | Player Two | Player Three | Player Four | Player Five",
                8.5,
                24,
                17,
                7,
                39.53,
            ),
        ],
        "stretches": [
            (
                1,
                0,
                2100,
                210.0,
                "Player One | Player Two | Player Three | Player Four | Player Five",
                10,
                5,
                5,
                0,
            ),
        ],
    }

    generated_path = generate_game_report(
        data=data,
        output_path=output_path,
    )

    assert generated_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 1_000

    reader = PdfReader(output_path)
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) >= 2
    assert "NBA ROTATION LAB" in extracted_text
    assert "Game Rotation Report" in extracted_text
    assert "NYK" in extracted_text
    assert "CHI" in extracted_text
    assert "Executive Readout" in extracted_text
    assert "Rotation Detail" in extracted_text
    assert "Methodology Note" in extracted_text

    pdf_bytes = generate_game_report_bytes(
        data=data,
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1_000

    memory_reader = PdfReader(BytesIO(pdf_bytes))

    assert len(memory_reader.pages) >= 2

    memory_text = "\n".join(page.extract_text() or "" for page in memory_reader.pages)

    assert "NBA ROTATION LAB" in memory_text
    assert "Game Rotation Report" in memory_text
    assert "Rotation Detail" in memory_text
