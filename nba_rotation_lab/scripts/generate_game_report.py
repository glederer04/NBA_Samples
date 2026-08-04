"""Generate a professional PDF report for one team-game."""

import argparse
from pathlib import Path

from rotation_lab.dashboard.data import get_game_review
from rotation_lab.reporting import generate_game_report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate an NBA Rotation Lab game report.",
    )
    parser.add_argument(
        "--team",
        required=True,
        help="Team abbreviation, such as NYK.",
    )
    parser.add_argument(
        "--game-id",
        required=True,
        help="NBA game identifier.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=("Optional output PDF path. Defaults to output/pdf/<team>_<game-id>_game_report.pdf."),
    )

    return parser.parse_args()


def main() -> None:
    """Generate the selected report."""

    args = parse_args()

    team_abbreviation = str(args.team).strip().upper()
    game_id = str(args.game_id).strip()

    data = get_game_review(
        team_abbreviation=team_abbreviation,
        game_id=game_id,
    )

    if data is None:
        raise SystemExit(f"No game-review data found for {team_abbreviation} and {game_id}.")

    output_path = args.output or Path(f"output/pdf/{team_abbreviation}_{game_id}_game_report.pdf")

    generated_path = generate_game_report(
        data=data,
        output_path=output_path,
    )

    print(f"Generated report: {generated_path.resolve()}")


if __name__ == "__main__":
    main()
