"""Read-only data access for the Dash application."""

from typing import Any

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import connect_database


def get_dashboard_teams() -> list[dict[str, str]]:
    """Return teams with game-review data."""

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT DISTINCT reviews.team_abbreviation
            FROM marts.team_game_review AS reviews
            INNER JOIN raw.teams AS featured_teams
                ON reviews.team_abbreviation = featured_teams.abbreviation
            ORDER BY reviews.team_abbreviation
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        {
            "label": str(row[0]),
            "value": str(row[0]),
        }
        for row in rows
    ]


def get_team_overview(
    team_abbreviation: str,
) -> dict[str, Any]:
    """Return executive-level rotation information for one team."""

    normalized_team = team_abbreviation.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS covered_games,
                COUNT_IF(result = 'W') AS wins,
                COUNT_IF(result = 'L') AS losses,
                SUM(plus_minus) AS cumulative_margin,
                ROUND(
                    AVG(lineups_used),
                    1
                ) AS average_lineups_used,
                ROUND(
                    AVG(lineup_changes),
                    1
                ) AS average_lineup_changes,
                COUNT_IF(score_matches)
                    AS validated_games
            FROM marts.team_game_review
            WHERE team_abbreviation = ?
            """,
            [normalized_team],
        ).fetchone()

        recent_games = connection.execute(
            """
            SELECT
                game_id,
                game_date,
                opponent_team_abbreviation,
                team_location,
                result,
                points_for,
                points_against,
                plus_minus,
                lineups_used,
                best_period,
                worst_period
            FROM marts.team_game_review
            WHERE team_abbreviation = ?
            ORDER BY
                game_date DESC,
                game_id DESC
            LIMIT 6
            """,
            [normalized_team],
        ).fetchall()

        top_lineups = connection.execute(
            """
            SELECT
                lineup_key,
                lineup_names,
                games_used,
                total_minutes,
                points_for,
                points_against,
                plus_minus,
                plus_minus_per_48,
                sample_size_status
            FROM marts.team_lineup_performance
            WHERE
                team_abbreviation = ?
                AND total_minutes >= 5
            ORDER BY
                total_minutes DESC,
                lineup_key
            LIMIT 5
            """,
            [normalized_team],
        ).fetchall()
    finally:
        connection.close()

    if summary is None:
        summary = (
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

    return {
        "team_abbreviation": normalized_team,
        "covered_games": int(summary[0] or 0),
        "wins": int(summary[1] or 0),
        "losses": int(summary[2] or 0),
        "cumulative_margin": int(summary[3] or 0),
        "average_lineups_used": float(summary[4] or 0),
        "average_lineup_changes": float(summary[5] or 0),
        "validated_games": int(summary[6] or 0),
        "recent_games": recent_games,
        "top_lineups": top_lineups,
    }


def get_team_games(
    team_abbreviation: str,
) -> list[dict[str, str]]:
    """Return dashboard game options for one team."""

    normalized_team = team_abbreviation.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                game_id,
                game_date,
                opponent_team_abbreviation,
                team_location,
                result,
                points_for,
                points_against
            FROM marts.team_game_review
            WHERE team_abbreviation = ?
            ORDER BY
                game_date DESC,
                game_id DESC
            """,
            [normalized_team],
        ).fetchall()
    finally:
        connection.close()

    options = []

    for row in rows:
        (
            game_id,
            game_date,
            opponent,
            team_location,
            result,
            points_for,
            points_against,
        ) = row

        location = "vs." if team_location == "home" else "at"

        options.append(
            {
                "label": (
                    f"{game_date} | {location} {opponent} | {result} {points_for}-{points_against}"
                ),
                "value": str(game_id),
            }
        )

    return options


def get_game_review(
    team_abbreviation: str,
    game_id: str,
) -> dict[str, Any] | None:
    """Return one team's complete game-review dataset."""

    normalized_team = team_abbreviation.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        summary = connection.execute(
            """
            SELECT
                game_id,
                game_date,
                team_abbreviation,
                opponent_team_abbreviation,
                team_location,
                result,
                points_for,
                points_against,
                plus_minus,
                rotation_intervals,
                lineups_used,
                lineup_changes,
                boundary_scoring_points,
                best_period,
                best_period_plus_minus,
                worst_period,
                worst_period_plus_minus,
                score_matches
            FROM marts.team_game_review
            WHERE
                team_abbreviation = ?
                AND game_id = ?
            """,
            [
                normalized_team,
                game_id,
            ],
        ).fetchone()

        if summary is None:
            return None

        periods = connection.execute(
            """
            SELECT
                period,
                points_for,
                points_against,
                plus_minus,
                lineups_used,
                rotation_intervals
            FROM marts.team_game_period_performance
            WHERE
                team_abbreviation = ?
                AND game_id = ?
            ORDER BY period
            """,
            [
                normalized_team,
                game_id,
            ],
        ).fetchall()

        lineups = connection.execute(
            """
            SELECT
                lineup_key,
                lineup_names,
                total_minutes,
                points_for,
                points_against,
                plus_minus,
                ROUND(
                    48.0
                    * plus_minus
                    / NULLIF(total_minutes, 0),
                    2
                ) AS plus_minus_per_48
            FROM marts.team_game_lineup_performance
            WHERE
                team_abbreviation = ?
                AND game_id = ?
            ORDER BY
                total_minutes DESC,
                lineup_key
            LIMIT 5
            """,
            [
                normalized_team,
                game_id,
            ],
        ).fetchall()

        stretches = connection.execute(
            """
            SELECT
                period,
                interval_start_deciseconds,
                interval_end_deciseconds,
                duration_seconds,
                lineup_names,
                points_for,
                points_against,
                plus_minus,
                boundary_scoring_points
            FROM marts.team_game_rotation_stretches
            WHERE
                team_abbreviation = ?
                AND game_id = ?
                AND duration_seconds >= 60
            ORDER BY interval_number
            """,
            [
                normalized_team,
                game_id,
            ],
        ).fetchall()
    finally:
        connection.close()

    return {
        "game_id": str(summary[0]),
        "game_date": summary[1],
        "team_abbreviation": str(summary[2]),
        "opponent": str(summary[3]),
        "team_location": str(summary[4]),
        "result": str(summary[5]),
        "points_for": int(summary[6]),
        "points_against": int(summary[7]),
        "plus_minus": int(summary[8]),
        "rotation_intervals": int(summary[9]),
        "lineups_used": int(summary[10]),
        "lineup_changes": int(summary[11]),
        "boundary_scoring_points": int(summary[12]),
        "best_period": int(summary[13]),
        "best_period_plus_minus": int(summary[14]),
        "worst_period": int(summary[15]),
        "worst_period_plus_minus": int(summary[16]),
        "score_matches": bool(summary[17]),
        "periods": periods,
        "lineups": lineups,
        "stretches": stretches,
    }


def get_team_players(
    team_abbreviation: str,
) -> list[dict[str, str]]:
    """Return players found in one team's rotation data."""

    normalized_team = team_abbreviation.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                rotation.player_id,
                MAX(rotation.player_name) AS player_name,
                ROUND(
                    SUM(rotation.duration_seconds) / 60.0,
                    1
                ) AS total_minutes
            FROM raw.rotation_stints AS rotation
            INNER JOIN raw.games AS games
                ON rotation.game_id = games.game_id
            WHERE
                (
                    rotation.team_id = games.home_team_id
                    AND games.home_team_abbreviation = ?
                )
                OR (
                    rotation.team_id = games.away_team_id
                    AND games.away_team_abbreviation = ?
                )
            GROUP BY rotation.player_id
            ORDER BY
                total_minutes DESC,
                player_name
            """,
            [
                normalized_team,
                normalized_team,
            ],
        ).fetchall()
    finally:
        connection.close()

    return [
        {
            "label": (f"{player_name} — {float(total_minutes):.1f} min"),
            "value": str(player_id),
        }
        for player_id, player_name, total_minutes in rows
    ]


def get_lineup_explorer(
    team_abbreviation: str,
    minimum_minutes: float = 0,
    player_ids: list[str] | None = None,
) -> list[tuple]:
    """Return team lineups matching minutes and player filters."""

    if minimum_minutes < 0:
        raise ValueError("minimum_minutes cannot be negative")

    normalized_team = team_abbreviation.strip().upper()
    selected_player_ids = player_ids or []

    conditions = [
        "team_abbreviation = ?",
        "total_minutes >= ?",
    ]
    parameters: list[object] = [
        normalized_team,
        minimum_minutes,
    ]

    for player_id in selected_player_ids:
        conditions.append(
            """
            LIST_CONTAINS(
                STRING_SPLIT(lineup_key, '-'),
                ?
            )
            """
        )
        parameters.append(str(player_id))

    query = f"""
        SELECT
            lineup_key,
            lineup_names,
            games_used,
            stint_appearances,
            total_minutes,
            points_for,
            points_against,
            plus_minus,
            plus_minus_per_48,
            offensive_points_per_48,
            defensive_points_per_48,
            boundary_scoring_points,
            sample_size_status
        FROM marts.team_lineup_performance
        WHERE {" AND ".join(conditions)}
        ORDER BY
            total_minutes DESC,
            lineup_key
    """

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()
    finally:
        connection.close()

    return rows


def get_rotation_timeline(
    team_abbreviation: str,
    game_id: str,
) -> dict[str, Any] | None:
    """Return player stints and substitutions for one team-game."""

    normalized_team = team_abbreviation.strip().upper()

    connection = connect_database(
        DATABASE_PATH,
        read_only=True,
    )

    try:
        summary = connection.execute(
            """
            SELECT
                team_id,
                team_abbreviation,
                opponent_team_abbreviation,
                team_location,
                game_date,
                result,
                points_for,
                points_against,
                plus_minus,
                lineups_used,
                lineup_changes
            FROM marts.team_game_review
            WHERE
                team_abbreviation = ?
                AND game_id = ?
            """,
            [
                normalized_team,
                game_id,
            ],
        ).fetchone()

        if summary is None:
            return None

        team_id = int(summary[0])

        stints = connection.execute(
            """
            SELECT
                player_id,
                player_name,
                stint_number,
                in_time_seconds,
                out_time_seconds,
                duration_seconds
            FROM raw.rotation_stints
            WHERE
                game_id = ?
                AND team_id = ?
            ORDER BY
                player_name,
                in_time_seconds,
                stint_number
            """,
            [
                game_id,
                team_id,
            ],
        ).fetchall()

        substitutions = connection.execute(
            """
            SELECT
                period,
                clock,
                game_elapsed_deciseconds,
                player_id,
                player_name,
                description
            FROM raw.play_by_play_events
            WHERE
                game_id = ?
                AND team_id = ?
                AND action_type = 'Substitution'
            ORDER BY
                game_elapsed_deciseconds,
                action_number,
                action_id
            """,
            [
                game_id,
                team_id,
            ],
        ).fetchall()
    finally:
        connection.close()

    if not stints:
        return None

    game_end_seconds = max(float(row[4]) for row in stints)

    return {
        "game_id": game_id,
        "team_id": team_id,
        "team_abbreviation": str(summary[1]),
        "opponent": str(summary[2]),
        "team_location": str(summary[3]),
        "game_date": summary[4],
        "result": str(summary[5]),
        "points_for": int(summary[6]),
        "points_against": int(summary[7]),
        "plus_minus": int(summary[8]),
        "lineups_used": int(summary[9]),
        "lineup_changes": int(summary[10]),
        "game_end_seconds": game_end_seconds,
        "stints": stints,
        "substitutions": substitutions,
    }
