CREATE OR REPLACE VIEW marts.rotation_coverage AS
WITH rotation_counts AS (
    SELECT
        game_id,
        COUNT(*) AS stint_records,
        COUNT(DISTINCT team_id) AS team_records,
        COUNT(DISTINCT player_id) AS player_records,
        ROUND(
            SUM(duration_seconds) / 60.0,
            2
        ) AS total_player_minutes
    FROM raw.rotation_stints
    GROUP BY game_id
)

SELECT
    games.game_id,
    games.game_date,
    games.season_id,
    games.season_type,
    games.home_team_abbreviation,
    games.away_team_abbreviation,
    COALESCE(counts.stint_records, 0) AS stint_records,
    COALESCE(counts.team_records, 0) AS team_records,
    COALESCE(counts.player_records, 0) AS player_records,
    COALESCE(counts.total_player_minutes, 0)
        AS total_player_minutes,
    CASE
        WHEN counts.game_id IS NULL
            THEN 'missing'
        WHEN
            counts.team_records = 2
            AND counts.player_records >= 10
            THEN 'complete'
        ELSE 'incomplete'
    END AS coverage_status
FROM raw.games AS games
LEFT JOIN rotation_counts AS counts
    ON games.game_id = counts.game_id;


CREATE OR REPLACE VIEW marts.rotation_coverage_summary AS
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
    SUM(
        CASE
            WHEN coverage_status = 'missing' THEN 1
            ELSE 0
        END
    ) AS missing_games,
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
FROM marts.rotation_coverage;


CREATE OR REPLACE VIEW marts.team_rotation_coverage AS
WITH team_games AS (
    SELECT
        game_id,
        home_team_id AS team_id,
        home_team_abbreviation AS team_abbreviation
    FROM raw.games

    UNION ALL

    SELECT
        game_id,
        away_team_id AS team_id,
        away_team_abbreviation AS team_abbreviation
    FROM raw.games
)

SELECT
    team_games.team_id,
    team_games.team_abbreviation,
    COUNT(*) AS total_games,
    SUM(
        CASE
            WHEN coverage.coverage_status = 'complete' THEN 1
            ELSE 0
        END
    ) AS covered_games,
    SUM(
        CASE
            WHEN coverage.coverage_status != 'complete' THEN 1
            ELSE 0
        END
    ) AS missing_games,
    ROUND(
        100.0
        * SUM(
            CASE
                WHEN coverage.coverage_status = 'complete' THEN 1
                ELSE 0
            END
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS coverage_percentage
FROM team_games
INNER JOIN marts.rotation_coverage AS coverage
    ON team_games.game_id = coverage.game_id
GROUP BY
    team_games.team_id,
    team_games.team_abbreviation;