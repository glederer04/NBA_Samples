CREATE OR REPLACE VIEW marts.team_game_lineup_performance AS
SELECT
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    team_location,
    opponent_team_id,
    opponent_team_abbreviation,
    lineup_key,
    MAX(lineup_names) AS lineup_names,
    COUNT(*) AS stint_appearances,
    ROUND(
        SUM(duration_seconds) / 60.0,
        2
    ) AS total_minutes,
    SUM(scoring_event_count) AS scoring_event_count,
    SUM(points_for) AS points_for,
    SUM(points_against) AS points_against,
    SUM(points_for)
        - SUM(points_against)
        AS plus_minus,
    SUM(boundary_scoring_points)
        AS boundary_scoring_points
FROM intermediate.team_lineup_interval_scoring
GROUP BY
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    team_location,
    opponent_team_id,
    opponent_team_abbreviation,
    lineup_key;


CREATE OR REPLACE VIEW marts.team_lineup_performance AS
SELECT
    team_id,
    team_abbreviation,
    lineup_key,
    MAX(lineup_names) AS lineup_names,
    COUNT(DISTINCT game_id) AS games_used,
    SUM(stint_appearances) AS stint_appearances,
    ROUND(
        SUM(total_minutes),
        2
    ) AS total_minutes,
    SUM(points_for) AS points_for,
    SUM(points_against) AS points_against,
    SUM(plus_minus) AS plus_minus,
    ROUND(
        48.0
        * SUM(plus_minus)
        / NULLIF(SUM(total_minutes), 0),
        2
    ) AS plus_minus_per_48,
    ROUND(
        48.0
        * SUM(points_for)
        / NULLIF(SUM(total_minutes), 0),
        2
    ) AS offensive_points_per_48,
    ROUND(
        48.0
        * SUM(points_against)
        / NULLIF(SUM(total_minutes), 0),
        2
    ) AS defensive_points_per_48,
    SUM(boundary_scoring_points)
        AS boundary_scoring_points,
    CASE
        WHEN SUM(total_minutes) >= 100
            THEN 'established'
        WHEN SUM(total_minutes) >= 25
            THEN 'directional'
        ELSE 'preliminary'
    END AS sample_size_status,
    MAX(game_date) AS latest_game_date
FROM marts.team_game_lineup_performance
GROUP BY
    team_id,
    team_abbreviation,
    lineup_key;


CREATE OR REPLACE VIEW marts.lineup_scoring_validation AS
WITH team_game_totals AS (
    SELECT
        game_id,
        team_id,
        team_abbreviation,
        team_location,
        SUM(points_for) AS calculated_points_for,
        SUM(points_against) AS calculated_points_against,
        SUM(boundary_scoring_points)
            AS boundary_scoring_points
    FROM marts.team_game_lineup_performance
    GROUP BY
        game_id,
        team_id,
        team_abbreviation,
        team_location
)

SELECT
    games.game_id,
    games.game_date,
    games.home_team_abbreviation,
    games.away_team_abbreviation,
    games.home_score AS official_home_score,
    games.away_score AS official_away_score,
    MAX(
        CASE
            WHEN totals.team_location = 'home'
                THEN totals.calculated_points_for
        END
    ) AS calculated_home_score,
    MAX(
        CASE
            WHEN totals.team_location = 'away'
                THEN totals.calculated_points_for
        END
    ) AS calculated_away_score,
    MAX(
        CASE
            WHEN totals.team_location = 'home'
                THEN totals.boundary_scoring_points
        END
    ) AS home_boundary_scoring_points,
    MAX(
        CASE
            WHEN totals.team_location = 'away'
                THEN totals.boundary_scoring_points
        END
    ) AS away_boundary_scoring_points,
    (
        games.home_score
        = MAX(
            CASE
                WHEN totals.team_location = 'home'
                    THEN totals.calculated_points_for
            END
        )
        AND games.away_score
        = MAX(
            CASE
                WHEN totals.team_location = 'away'
                    THEN totals.calculated_points_for
            END
        )
    ) AS score_matches
FROM raw.games AS games
INNER JOIN team_game_totals AS totals
    ON games.game_id = totals.game_id
GROUP BY
    games.game_id,
    games.game_date,
    games.home_team_abbreviation,
    games.away_team_abbreviation,
    games.home_score,
    games.away_score;