CREATE OR REPLACE VIEW marts.team_lineup_interval_coverage AS
SELECT
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    opponent_team_abbreviation,
    COUNT(*) AS total_intervals,
    SUM(
        CASE
            WHEN player_count = 5 THEN 1
            ELSE 0
        END
    ) AS valid_intervals,
    SUM(
        CASE
            WHEN player_count != 5 THEN 1
            ELSE 0
        END
    ) AS invalid_intervals,
    ROUND(
        SUM(duration_seconds),
        2
    ) AS game_duration_seconds,
    ROUND(
        SUM(
            CASE
                WHEN player_count = 5
                    THEN duration_seconds
                ELSE 0
            END
        ),
        2
    ) AS valid_duration_seconds,
    ROUND(
        SUM(
            CASE
                WHEN player_count != 5
                    THEN duration_seconds
                ELSE 0
            END
        ),
        2
    ) AS invalid_duration_seconds,
    ROUND(
        100.0
        * SUM(
            CASE
                WHEN player_count = 5
                    THEN duration_seconds
                ELSE 0
            END
        )
        / NULLIF(SUM(duration_seconds), 0),
        2
    ) AS coverage_percentage,
    CASE
        WHEN SUM(
            CASE
                WHEN player_count != 5 THEN 1
                ELSE 0
            END
        ) = 0
            THEN 'complete'
        ELSE 'incomplete'
    END AS coverage_status
FROM intermediate.all_team_lineup_intervals
GROUP BY
    game_id,
    game_date,
    team_id,
    team_abbreviation,
    opponent_team_abbreviation;


CREATE OR REPLACE VIEW marts.game_lineup_interval_coverage AS
SELECT
    game_id,
    game_date,
    COUNT(*) AS team_records,
    SUM(total_intervals) AS total_intervals,
    SUM(valid_intervals) AS valid_intervals,
    SUM(invalid_intervals) AS invalid_intervals,
    ROUND(
        MIN(coverage_percentage),
        2
    ) AS minimum_team_coverage_percentage,
    CASE
        WHEN
            COUNT(*) = 2
            AND SUM(invalid_intervals) = 0
            THEN 'complete'
        ELSE 'incomplete'
    END AS coverage_status
FROM marts.team_lineup_interval_coverage
GROUP BY
    game_id,
    game_date;


CREATE OR REPLACE VIEW marts.lineup_interval_coverage_summary AS
SELECT
    COUNT(*) AS total_games,
    SUM(
        CASE
            WHEN coverage_status = 'complete' THEN 1
            ELSE 0
        END
    ) AS complete_games,
    SUM(
        CASE
            WHEN coverage_status = 'incomplete' THEN 1
            ELSE 0
        END
    ) AS incomplete_games,
    ROUND(
        100.0
        * SUM(
            CASE
                WHEN coverage_status = 'complete' THEN 1
                ELSE 0
            END
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS coverage_percentage
FROM marts.game_lineup_interval_coverage;