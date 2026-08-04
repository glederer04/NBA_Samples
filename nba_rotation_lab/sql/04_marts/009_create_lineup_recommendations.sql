CREATE OR REPLACE VIEW marts.lineup_recommendation_pool AS
WITH team_baselines AS (
    SELECT
        team_id,
        team_abbreviation,
        ROUND(
            48.0
            * SUM(plus_minus)
            / NULLIF(SUM(total_minutes), 0),
            2
        ) AS team_plus_minus_per_48
    FROM marts.team_lineup_performance
    GROUP BY
        team_id,
        team_abbreviation
),

shrunk_lineups AS (
    SELECT
        performance.team_id,
        performance.team_abbreviation,
        performance.lineup_key,
        performance.lineup_names,
        performance.games_used,
        performance.stint_appearances,
        performance.total_minutes,
        performance.points_for,
        performance.points_against,
        performance.plus_minus,
        performance.plus_minus_per_48,
        performance.offensive_points_per_48,
        performance.defensive_points_per_48,
        performance.sample_size_status,
        performance.latest_game_date,
        baseline.team_plus_minus_per_48,
        ROUND(
            100.0
            * performance.total_minutes
            / (performance.total_minutes + 48.0),
            2
        ) AS confidence_percentage,
        ROUND(
            (
                performance.total_minutes
                / (performance.total_minutes + 48.0)
            )
            * performance.plus_minus_per_48
            + (
                48.0
                / (performance.total_minutes + 48.0)
            )
            * baseline.team_plus_minus_per_48,
            2
        ) AS adjusted_plus_minus_per_48
    FROM marts.team_lineup_performance AS performance
    INNER JOIN team_baselines AS baseline
        ON performance.team_id = baseline.team_id
    WHERE performance.total_minutes >= 5
),

labeled_lineups AS (
    SELECT
        *,
        CASE
            WHEN total_minutes < 15
                THEN 'exploratory'
            WHEN
                adjusted_plus_minus_per_48
                >= team_plus_minus_per_48 + 3
                THEN 'prioritize'
            WHEN
                adjusted_plus_minus_per_48
                <= team_plus_minus_per_48 - 3
                THEN 'limit'
            ELSE 'monitor'
        END AS recommendation
    FROM shrunk_lineups
)

SELECT
    *,
    ROW_NUMBER() OVER (
        PARTITION BY team_id
        ORDER BY
            adjusted_plus_minus_per_48 DESC,
            total_minutes DESC
    ) AS recommendation_rank
FROM labeled_lineups;