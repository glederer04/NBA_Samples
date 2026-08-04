CREATE OR REPLACE VIEW intermediate.all_team_lineup_intervals AS
WITH rotation_boundaries AS (
    SELECT
        game_id,
        team_id,
        in_time_deciseconds AS boundary_time
    FROM raw.rotation_stints

    UNION

    SELECT
        game_id,
        team_id,
        out_time_deciseconds AS boundary_time
    FROM raw.rotation_stints
),

raw_intervals AS (
    SELECT
        game_id,
        team_id,
        boundary_time AS interval_start_deciseconds,
        LEAD(boundary_time) OVER (
            PARTITION BY
                game_id,
                team_id
            ORDER BY boundary_time
        ) AS interval_end_deciseconds
    FROM rotation_boundaries
),

active_players AS (
    SELECT DISTINCT
        intervals.game_id,
        intervals.team_id,
        intervals.interval_start_deciseconds,
        intervals.interval_end_deciseconds,
        rotation_stints.player_id,
        rotation_stints.player_name
    FROM raw_intervals AS intervals
    LEFT JOIN raw.rotation_stints AS rotation_stints
        ON intervals.game_id = rotation_stints.game_id
        AND intervals.team_id = rotation_stints.team_id
        AND rotation_stints.in_time_deciseconds
            <= intervals.interval_start_deciseconds
        AND rotation_stints.out_time_deciseconds
            >= intervals.interval_end_deciseconds
    WHERE
        intervals.interval_end_deciseconds
            > intervals.interval_start_deciseconds
),

grouped_intervals AS (
    SELECT
        game_id,
        team_id,
        interval_start_deciseconds,
        interval_end_deciseconds,
        COUNT(player_id) AS player_count,
        STRING_AGG(
            CAST(player_id AS VARCHAR),
            '-'
            ORDER BY player_id
        ) AS lineup_key,
        STRING_AGG(
            player_name,
            ' | '
            ORDER BY player_id
        ) AS lineup_names
    FROM active_players
    GROUP BY
        game_id,
        team_id,
        interval_start_deciseconds,
        interval_end_deciseconds
),

enriched_intervals AS (
    SELECT
        intervals.game_id,
        games.game_date,
        intervals.team_id,
        CASE
            WHEN intervals.team_id = games.home_team_id
                THEN games.home_team_abbreviation
            WHEN intervals.team_id = games.away_team_id
                THEN games.away_team_abbreviation
        END AS team_abbreviation,
        CASE
            WHEN intervals.team_id = games.home_team_id
                THEN 'home'
            WHEN intervals.team_id = games.away_team_id
                THEN 'away'
        END AS team_location,
        CASE
            WHEN intervals.team_id = games.home_team_id
                THEN games.away_team_id
            WHEN intervals.team_id = games.away_team_id
                THEN games.home_team_id
        END AS opponent_team_id,
        CASE
            WHEN intervals.team_id = games.home_team_id
                THEN games.away_team_abbreviation
            WHEN intervals.team_id = games.away_team_id
                THEN games.home_team_abbreviation
        END AS opponent_team_abbreviation,
        intervals.interval_start_deciseconds,
        intervals.interval_end_deciseconds,
        intervals.interval_start_deciseconds / 10.0
            AS interval_start_seconds,
        intervals.interval_end_deciseconds / 10.0
            AS interval_end_seconds,
        (
            intervals.interval_end_deciseconds
            - intervals.interval_start_deciseconds
        ) / 10.0 AS duration_seconds,
        CASE
            WHEN intervals.interval_start_deciseconds < 28800
                THEN CAST(
                    FLOOR(
                        intervals.interval_start_deciseconds
                        / 7200
                    ) + 1
                    AS INTEGER
                )
            ELSE CAST(
                FLOOR(
                    (
                        intervals.interval_start_deciseconds
                        - 28800
                    ) / 3000
                ) + 5
                AS INTEGER
            )
        END AS period,
        CASE
            WHEN intervals.interval_start_deciseconds < 28800
                THEN ROUND(
                    720.0
                    - (
                        intervals.interval_start_deciseconds
                        % 7200
                    ) / 10.0,
                    1
                )
            ELSE ROUND(
                300.0
                - (
                    (
                        intervals.interval_start_deciseconds
                        - 28800
                    ) % 3000
                ) / 10.0,
                1
            )
        END AS period_clock_remaining_seconds,
        intervals.player_count,
        intervals.lineup_key,
        intervals.lineup_names
    FROM grouped_intervals AS intervals
    INNER JOIN raw.games AS games
        ON intervals.game_id = games.game_id
)

SELECT
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    team_location,
    opponent_team_id,
    opponent_team_abbreviation,
    ROW_NUMBER() OVER (
        PARTITION BY
            game_id,
            team_id
        ORDER BY
            interval_start_deciseconds,
            interval_end_deciseconds
    ) AS interval_number,
    period,
    period_clock_remaining_seconds,
    interval_start_deciseconds,
    interval_end_deciseconds,
    interval_start_seconds,
    interval_end_seconds,
    duration_seconds,
    player_count,
    lineup_key,
    lineup_names
FROM enriched_intervals;


CREATE OR REPLACE VIEW intermediate.team_lineup_intervals AS
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
    period_clock_remaining_seconds,
    interval_start_deciseconds,
    interval_end_deciseconds,
    interval_start_seconds,
    interval_end_seconds,
    duration_seconds,
    lineup_key,
    lineup_names
FROM intermediate.all_team_lineup_intervals
WHERE player_count = 5;