CREATE OR REPLACE VIEW marts.team_game_lineups AS
WITH team_game_ends AS (
    SELECT
        game_id,
        team_id,
        MAX(interval_end_deciseconds)
            AS game_end_deciseconds
    FROM intermediate.team_lineup_intervals
    GROUP BY
        game_id,
        team_id
)

SELECT
    intervals.game_id,
    intervals.game_date,
    intervals.team_id,
    intervals.team_abbreviation,
    intervals.opponent_team_id,
    intervals.opponent_team_abbreviation,
    intervals.lineup_key,
    MAX(intervals.lineup_names) AS lineup_names,
    COUNT(*) AS stint_appearances,
    ROUND(
        SUM(intervals.duration_seconds) / 60.0,
        2
    ) AS total_minutes,
    MIN(intervals.interval_start_deciseconds)
        AS first_entry_deciseconds,
    MAX(intervals.interval_end_deciseconds)
        AS final_exit_deciseconds,
    MIN(intervals.interval_start_deciseconds) = 0
        AS is_opening_lineup,
    MAX(intervals.interval_end_deciseconds)
        = game_ends.game_end_deciseconds
        AS is_closing_lineup,
    ROUND(
        SUM(
            CASE
                WHEN intervals.interval_end_deciseconds <= 25800
                    THEN 0
                WHEN intervals.interval_start_deciseconds < 28800
                    THEN (
                        LEAST(
                            intervals.interval_end_deciseconds,
                            28800
                        )
                        - GREATEST(
                            intervals.interval_start_deciseconds,
                            25800
                        )
                    ) / 10.0
                ELSE intervals.duration_seconds
            END
        ) / 60.0,
        2
    ) AS closing_minutes
FROM intermediate.team_lineup_intervals AS intervals
INNER JOIN team_game_ends AS game_ends
    ON intervals.game_id = game_ends.game_id
    AND intervals.team_id = game_ends.team_id
GROUP BY
    intervals.game_id,
    intervals.game_date,
    intervals.team_id,
    intervals.team_abbreviation,
    intervals.opponent_team_id,
    intervals.opponent_team_abbreviation,
    intervals.lineup_key,
    game_ends.game_end_deciseconds;


CREATE OR REPLACE VIEW marts.team_lineup_usage AS
WITH team_totals AS (
    SELECT
        team_id,
        team_abbreviation,
        COUNT(DISTINCT game_id) AS covered_games,
        SUM(total_minutes) AS team_total_minutes
    FROM marts.team_game_lineups
    GROUP BY
        team_id,
        team_abbreviation
),

lineup_summaries AS (
    SELECT
        lineups.team_id,
        lineups.team_abbreviation,
        lineups.lineup_key,
        MAX(lineups.lineup_names) AS lineup_names,
        totals.covered_games,
        COUNT(DISTINCT lineups.game_id) AS games_used,
        SUM(lineups.stint_appearances)
            AS stint_appearances,
        ROUND(
            SUM(lineups.total_minutes),
            2
        ) AS total_minutes,
        ROUND(
            AVG(lineups.total_minutes),
            2
        ) AS average_minutes_per_game_used,
        SUM(
            CASE
                WHEN lineups.is_opening_lineup THEN 1
                ELSE 0
            END
        ) AS opening_games,
        SUM(
            CASE
                WHEN lineups.is_closing_lineup THEN 1
                ELSE 0
            END
        ) AS closing_games,
        ROUND(
            SUM(lineups.closing_minutes),
            2
        ) AS closing_minutes,
        ROUND(
            100.0
            * SUM(lineups.total_minutes)
            / NULLIF(totals.team_total_minutes, 0),
            2
        ) AS total_minutes_percentage,
        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN lineups.is_opening_lineup THEN 1
                    ELSE 0
                END
            )
            / NULLIF(totals.covered_games, 0),
            2
        ) AS opening_game_percentage,
        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN lineups.is_closing_lineup THEN 1
                    ELSE 0
                END
            )
            / NULLIF(totals.covered_games, 0),
            2
        ) AS closing_game_percentage,
        MAX(lineups.game_date) AS latest_game_date
    FROM marts.team_game_lineups AS lineups
    INNER JOIN team_totals AS totals
        ON lineups.team_id = totals.team_id
    GROUP BY
        lineups.team_id,
        lineups.team_abbreviation,
        lineups.lineup_key,
        totals.covered_games,
        totals.team_total_minutes
)

SELECT
    team_id,
    team_abbreviation,
    lineup_key,
    lineup_names,
    covered_games,
    games_used,
    stint_appearances,
    total_minutes,
    average_minutes_per_game_used,
    total_minutes_percentage,
    opening_games,
    opening_game_percentage,
    closing_games,
    closing_game_percentage,
    closing_minutes,
    CASE
        WHEN total_minutes_percentage >= 20
            THEN 'primary'
        WHEN total_minutes_percentage >= 10
            THEN 'secondary'
        ELSE 'situational'
    END AS lineup_role,
    CASE
        WHEN games_used >= 10
            THEN 'established'
        WHEN games_used >= 5
            THEN 'directional'
        ELSE 'preliminary'
    END AS sample_size_status,
    latest_game_date
FROM lineup_summaries;


CREATE OR REPLACE VIEW marts.team_lineup_continuity AS
WITH game_lineup_counts AS (
    SELECT
        team_id,
        team_abbreviation,
        game_id,
        COUNT(*) AS lineups_used
    FROM marts.team_game_lineups
    GROUP BY
        team_id,
        team_abbreviation,
        game_id
),

team_summaries AS (
    SELECT
        lineups.team_id,
        lineups.team_abbreviation,
        COUNT(DISTINCT lineups.game_id)
            AS covered_games,
        COUNT(DISTINCT lineups.lineup_key)
            AS unique_lineups,
        COUNT(
            DISTINCT CASE
                WHEN lineups.is_opening_lineup
                    THEN lineups.lineup_key
            END
        ) AS opening_lineup_variants,
        COUNT(
            DISTINCT CASE
                WHEN lineups.is_closing_lineup
                    THEN lineups.lineup_key
            END
        ) AS closing_lineup_variants,
        ROUND(
            SUM(lineups.total_minutes),
            2
        ) AS total_lineup_minutes
    FROM marts.team_game_lineups AS lineups
    GROUP BY
        lineups.team_id,
        lineups.team_abbreviation
),

average_lineup_counts AS (
    SELECT
        team_id,
        team_abbreviation,
        ROUND(
            AVG(lineups_used),
            2
        ) AS average_lineups_per_game
    FROM game_lineup_counts
    GROUP BY
        team_id,
        team_abbreviation
),

ranked_lineups AS (
    SELECT
        team_id,
        team_abbreviation,
        lineup_key,
        lineup_names,
        total_minutes,
        total_minutes_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY team_id
            ORDER BY
                total_minutes DESC,
                lineup_key
        ) AS usage_rank
    FROM marts.team_lineup_usage
)

SELECT
    summaries.team_id,
    summaries.team_abbreviation,
    summaries.covered_games,
    summaries.unique_lineups,
    averages.average_lineups_per_game,
    summaries.opening_lineup_variants,
    summaries.closing_lineup_variants,
    summaries.total_lineup_minutes,
    ranked.lineup_key AS most_used_lineup_key,
    ranked.lineup_names AS most_used_lineup_names,
    ranked.total_minutes AS most_used_lineup_minutes,
    ranked.total_minutes_percentage
        AS most_used_lineup_percentage,
    CASE
        WHEN ranked.total_minutes_percentage >= 25
            THEN 'stable'
        WHEN ranked.total_minutes_percentage >= 15
            THEN 'moderate'
        ELSE 'fluid'
    END AS continuity_style,
    CASE
        WHEN summaries.covered_games >= 10
            THEN 'established'
        WHEN summaries.covered_games >= 5
            THEN 'directional'
        ELSE 'preliminary'
    END AS sample_size_status
FROM team_summaries AS summaries
INNER JOIN average_lineup_counts AS averages
    ON summaries.team_id = averages.team_id
INNER JOIN ranked_lineups AS ranked
    ON summaries.team_id = ranked.team_id
    AND ranked.usage_rank = 1;