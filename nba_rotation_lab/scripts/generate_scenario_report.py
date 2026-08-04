"""Generate a professional PDF report for a rotation scenario."""

import argparse
from pathlib import Path

from rotation_lab.modeling import (
    LineupAllocation,
    project_rotation_plan,
)
from rotation_lab.recommendations import get_lineup_recommendations
from rotation_lab.reporting import generate_scenario_report


def parse_allocation(value: str) -> tuple[str, float]:
    """Parse LINEUP_KEY=MINUTES from the command line."""

    lineup_key, separator, minutes_text = value.rpartition("=")

    if not separator or not lineup_key.strip():
        raise argparse.ArgumentTypeError("allocation must use LINEUP_KEY=MINUTES format")

    try:
        minutes = float(minutes_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("allocation minutes must be numeric") from error

    if minutes <= 0:
        raise argparse.ArgumentTypeError("allocation minutes must be greater than zero")

    return lineup_key.strip(), minutes


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate an NBA Rotation Lab scenario report.",
    )
    parser.add_argument(
        "--team",
        required=True,
        help="Team abbreviation, such as NYK.",
    )
    parser.add_argument(
        "--allocation",
        action="append",
        required=True,
        type=parse_allocation,
        metavar="LINEUP_KEY=MINUTES",
        help=(
            "Lineup key and planned minutes. Repeat this option for each lineup in the scenario."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=("Optional output path. Defaults to output/pdf/<team>_rotation_scenario_report.pdf."),
    )

    return parser.parse_args()


def main() -> None:
    """Generate the selected scenario report."""

    args = parse_args()
    team_abbreviation = str(args.team).strip().upper()

    recommendations = get_lineup_recommendations(
        team_abbreviation,
        limit=50,
    )
    recommendations_by_key = {
        recommendation.lineup_key: recommendation for recommendation in recommendations
    }

    allocations = []

    for lineup_key, planned_minutes in args.allocation:
        recommendation = recommendations_by_key.get(lineup_key)

        if recommendation is None:
            raise SystemExit(
                f"No recommendation found for lineup {lineup_key} and team {team_abbreviation}."
            )

        allocations.append(
            LineupAllocation(
                recommendation=recommendation,
                planned_minutes=planned_minutes,
            )
        )

    try:
        projection = project_rotation_plan(allocations)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    output_path = args.output or Path(
        f"output/pdf/{team_abbreviation}_rotation_scenario_report.pdf"
    )

    generated_path = generate_scenario_report(
        allocations=allocations,
        projection=projection,
        output_path=output_path,
    )

    print(f"Generated report: {generated_path.resolve()}")


if __name__ == "__main__":
    main()
