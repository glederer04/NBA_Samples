"""Tests for professional rotation-scenario PDF reports."""

from datetime import date
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from rotation_lab.modeling import (
    LineupAllocation,
    project_rotation_plan,
)
from rotation_lab.recommendations import LineupRecommendation
from rotation_lab.reporting import (
    generate_scenario_report,
    generate_scenario_report_bytes,
)


def build_recommendation(
    *,
    lineup_key: str,
    rank: int,
    adjusted_plus_minus_per_48: float,
    confidence_percentage: float,
) -> LineupRecommendation:
    """Create one report-test lineup recommendation."""

    player_ids = lineup_key.split("-")

    return LineupRecommendation(
        team_abbreviation="NYK",
        recommendation_rank=rank,
        lineup_key=lineup_key,
        player_names=tuple(f"Player {player_id}" for player_id in player_ids),
        games_used=12,
        total_minutes=125.0,
        raw_plus_minus_per_48=10.0,
        adjusted_plus_minus_per_48=adjusted_plus_minus_per_48,
        team_plus_minus_per_48=4.0,
        confidence_percentage=confidence_percentage,
        recommendation="monitor",
        sample_size_status="established",
        latest_game_date=date(2026, 1, 15),
    )


def build_allocations() -> list[LineupAllocation]:
    """Create a complete 48-minute test scenario."""

    first = build_recommendation(
        lineup_key="1-2-3-4-5",
        rank=1,
        adjusted_plus_minus_per_48=8.0,
        confidence_percentage=60.0,
    )
    second = build_recommendation(
        lineup_key="6-7-8-9-10",
        rank=2,
        adjusted_plus_minus_per_48=6.0,
        confidence_percentage=50.0,
    )

    return [
        LineupAllocation(
            recommendation=first,
            planned_minutes=24.0,
        ),
        LineupAllocation(
            recommendation=second,
            planned_minutes=24.0,
        ),
    ]


def test_generate_scenario_report_creates_readable_pdf(
    tmp_path: Path,
) -> None:
    """The generated report should contain staff-facing content."""

    allocations = build_allocations()
    projection = project_rotation_plan(allocations)
    output_path = tmp_path / "scenario_report.pdf"

    generated_path = generate_scenario_report(
        allocations=allocations,
        projection=projection,
        output_path=output_path,
    )

    assert generated_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 1_000

    reader = PdfReader(output_path)
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) >= 2
    assert "NBA ROTATION LAB" in extracted_text
    assert "Rotation Scenario Report" in extracted_text
    assert "NYK" in extracted_text
    assert "Staff Readout" in extracted_text
    assert "Planned Allocation Summary" in extracted_text
    assert "Lineup Allocation Detail" in extracted_text
    assert "Player 1" in extracted_text
    assert "Methodology and Use" in extracted_text


def test_generate_scenario_report_bytes_returns_pdf() -> None:
    """The in-memory report should return a readable PDF."""

    allocations = build_allocations()
    projection = project_rotation_plan(allocations)

    pdf_bytes = generate_scenario_report_bytes(
        allocations=allocations,
        projection=projection,
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1_000

    reader = PdfReader(BytesIO(pdf_bytes))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) >= 2
    assert "Rotation Scenario Report" in extracted_text
    assert "Lineup Allocation Detail" in extracted_text
