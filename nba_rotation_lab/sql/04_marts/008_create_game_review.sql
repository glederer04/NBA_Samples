CREATE OR REPLACE VIEW marts.team_game_period_performance AS
SELECT
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    team_location,
    opponent_team_id,
    opponent_team_abbreviation,
    period,
    ROUND(
        SUM(duration_seconds) / 60.0,
        2
    ) AS total_minutes,
    COUNT(*) AS rotation_intervals,
    COUNT(DISTINCT lineup_key) AS lineups_used,
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
    period;


CREATE OR REPLACE VIEW marts.team_game_rotation_stretches AS
SELECT
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    team_location,
    opponent_team_id,
    opponent_team_abbreviation,
    interval_number,
    period,
    interval_start_deciseconds,
    interval_end_deciseconds,
    duration_seconds,
    lineup_key,
    lineup_names,
    scoring_event_count,
    points_for,
    points_against,
    points_for - points_against AS plus_minus,
    ROUND(
        48.0
        * (points_for - points_against)
        / NULLIF(duration_seconds / 60.0, 0),
        2
    ) AS plus_minus_per_48,
    boundary_scoring_points
FROM intermediate.team_lineup_interval_scoring;


CREATE OR REPLACE VIEW marts.team_game_review AS
WITH team_game_totals AS (
    SELECT
        game_id,
        game_date,
        team_id,
        team_abbreviation,
        team_location,
        opponent_team_id,
        opponent_team_abbreviation,
        ROUND(
            SUM(duration_seconds) / 60.0,
            2
        ) AS total_minutes,
        COUNT(*) AS rotation_intervals,
        COUNT(DISTINCT lineup_key) AS lineups_used,
        GREATEST(COUNT(*) - 1, 0)
            AS lineup_changes,
        SUM(points_for) AS points_for,
        SUM(points_against) AS points_against,
        SUM(points_for) - SUM(points_against)
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
        opponent_team_abbreviation
),

ranked_lineups AS (
    SELECT
        game_id,
        team_id,
        lineup_key,
        lineup_names,
        total_minutes,
        plus_minus,
        ROW_NUMBER() OVER (
            PARTITION BY
                game_id,
                team_id
            ORDER BY
                plus_minus DESC,
                total_minutes DESC,
                lineup_key
        ) AS best_rank,
        ROW_NUMBER() OVER (
            PARTITION BY
                game_id,
                team_id
            ORDER BY
                plus_minus,
                total_minutes DESC,
                lineup_key
        ) AS worst_rank
    FROM marts.team_game_lineup_performance
),

best_lineups AS (
    SELECT
        game_id,
        team_id,
        lineup_key,
        lineup_names,
        total_minutes,
        plus_minus
    FROM ranked_lineups
    WHERE best_rank = 1
),

worst_lineups AS (
    SELECT
        game_id,
        team_id,
        lineup_key,
        lineup_names,
        total_minutes,
        plus_minus
    FROM ranked_lineups
    WHERE worst_rank = 1
),

ranked_periods AS (
    SELECT
        game_id,
        team_id,
        period,
        points_for,
        points_against,
        plus_minus,
        ROW_NUMBER() OVER (
            PARTITION BY
                game_id,
                team_id
            ORDER BY
                plus_minus DESC,
                period
        ) AS best_rank,
        ROW_NUMBER() OVER (
            PARTITION BY
                game_id,
                team_id
            ORDER BY
                plus_minus,
                period
        ) AS worst_rank
    FROM marts.team_game_period_performance
),

best_periods AS (
    SELECT
        game_id,
        team_id,
        period,
        points_for,
        points_against,
        plus_minus
    FROM ranked_periods
    WHERE best_rank = 1
),

worst_periods AS (
    SELECT
        game_id,
        team_id,
        period,
        points_for,
        points_against,
        plus_minus
    FROM ranked_periods
    WHERE worst_rank = 1
)

SELECT
    totals.game_id,
    totals.game_date,
    totals.team_id,
    totals.team_abbreviation,
    totals.team_location,
    totals.opponent_team_id,
    totals.opponent_team_abbreviation,
    totals.points_for,
    totals.points_against,
    totals.plus_minus,
    CASE
        WHEN totals.plus_minus > 0
            THEN 'W'
        WHEN totals.plus_minus < 0
            THEN 'L'
        ELSE 'T'
    END AS result,
    totals.total_minutes,
    totals.rotation_intervals,
    totals.lineups_used,
    totals.lineup_changes,
    totals.boundary_scoring_points,
    best_lineups.lineup_key
        AS best_lineup_key,
    best_lineups.lineup_names
        AS best_lineup_names,
    best_lineups.total_minutes
        AS best_lineup_minutes,
    best_lineups.plus_minus
        AS best_lineup_plus_minus,
    worst_lineups.lineup_key
        AS worst_lineup_key,
    worst_lineups.lineup_names
        AS worst_lineup_names,
    worst_lineups.total_minutes
        AS worst_lineup_minutes,
    worst_lineups.plus_minus
        AS worst_lineup_plus_minus,
    best_periods.period
        AS best_period,
    best_periods.points_for
        AS best_period_points_for,
    best_periods.points_against
        AS best_period_points_against,
    best_periods.plus_minus
        AS best_period_plus_minus,
    worst_periods.period
        AS worst_period,
    worst_periods.points_for
        AS worst_period_points_for,
    worst_periods.points_against
        AS worst_period_points_against,
    worst_periods.plus_minus
        AS worst_period_plus_minus,
    validation.score_matches
FROM team_game_totals AS totals
INNER JOIN best_lineups
    ON totals.game_id = best_lineups.game_id
    AND totals.team_id = best_lineups.team_id
INNER JOIN worst_lineups
    ON totals.game_id = worst_lineups.game_id
    AND totals.team_id = worst_lineups.team_id
INNER JOIN best_periods
    ON totals.game_id = best_periods.game_id
    AND totals.team_id = best_periods.team_id
INNER JOIN worst_periods
    ON totals.game_id = worst_periods.game_id
    AND totals.team_id = worst_periods.team_id
INNER JOIN marts.lineup_scoring_validation AS validation
    ON totals.game_id = validation.game_id;