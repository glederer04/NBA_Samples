CREATE OR REPLACE VIEW intermediate.team_lineup_interval_scoring AS
WITH play_by_play_games AS (
    SELECT DISTINCT game_id
    FROM raw.play_by_play_events
)

SELECT
    intervals.game_id,
    intervals.game_date,
    intervals.team_id,
    intervals.team_abbreviation,
    intervals.team_location,
    intervals.opponent_team_id,
    intervals.opponent_team_abbreviation,
    intervals.interval_number,
    intervals.period,
    intervals.interval_start_deciseconds,
    intervals.interval_end_deciseconds,
    intervals.duration_seconds,
    intervals.lineup_key,
    intervals.lineup_names,
    COUNT(scoring.action_id) AS scoring_event_count,
    COALESCE(
        SUM(
            CASE
                WHEN intervals.team_location = 'home'
                    THEN scoring.home_points
                ELSE scoring.away_points
            END
        ),
        0
    ) AS points_for,
    COALESCE(
        SUM(
            CASE
                WHEN intervals.team_location = 'home'
                    THEN scoring.away_points
                ELSE scoring.home_points
            END
        ),
        0
    ) AS points_against,
    COALESCE(
        SUM(
            CASE
                WHEN
                    scoring.game_elapsed_deciseconds
                    = intervals.interval_end_deciseconds
                    THEN
                        scoring.home_points
                        + scoring.away_points
                ELSE 0
            END
        ),
        0
    ) AS boundary_scoring_points
FROM intermediate.team_lineup_intervals AS intervals
INNER JOIN play_by_play_games AS covered_games
    ON intervals.game_id = covered_games.game_id
LEFT JOIN staging.scoring_events AS scoring
    ON intervals.game_id = scoring.game_id
    AND scoring.game_elapsed_deciseconds
        > intervals.interval_start_deciseconds
    AND scoring.game_elapsed_deciseconds
        <= intervals.interval_end_deciseconds
GROUP BY
    intervals.game_id,
    intervals.game_date,
    intervals.team_id,
    intervals.team_abbreviation,
    intervals.team_location,
    intervals.opponent_team_id,
    intervals.opponent_team_abbreviation,
    intervals.interval_number,
    intervals.period,
    intervals.interval_start_deciseconds,
    intervals.interval_end_deciseconds,
    intervals.duration_seconds,
    intervals.lineup_key,
    intervals.lineup_names;