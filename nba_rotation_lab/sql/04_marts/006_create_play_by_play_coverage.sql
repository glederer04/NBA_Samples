CREATE OR REPLACE VIEW marts.play_by_play_coverage AS
WITH event_summaries AS (
    SELECT
        game_id,
        COUNT(*) AS event_count,
        MAX(period) AS maximum_period,
        MIN(game_elapsed_deciseconds)
            AS first_event_deciseconds,
        MAX(game_elapsed_deciseconds)
            AS final_event_deciseconds
    FROM raw.play_by_play_events
    GROUP BY game_id
),

ranked_scores AS (
    SELECT
        game_id,
        score_home,
        score_away,
        ROW_NUMBER() OVER (
            PARTITION BY game_id
            ORDER BY
                game_elapsed_deciseconds DESC,
                action_number DESC,
                action_id DESC
        ) AS score_rank
    FROM raw.play_by_play_events
    WHERE
        score_home IS NOT NULL
        AND score_away IS NOT NULL
),

final_scores AS (
    SELECT
        game_id,
        score_home AS play_by_play_home_score,
        score_away AS play_by_play_away_score
    FROM ranked_scores
    WHERE score_rank = 1
)

SELECT
    games.game_id,
    games.game_date,
    games.home_team_id,
    games.away_team_id,
    games.home_team_abbreviation,
    games.away_team_abbreviation,
    games.home_score AS official_home_score,
    games.away_score AS official_away_score,
    COALESCE(events.event_count, 0) AS event_count,
    events.maximum_period,
    events.first_event_deciseconds,
    events.final_event_deciseconds,
    scores.play_by_play_home_score,
    scores.play_by_play_away_score,
    events.game_id IS NOT NULL AS has_play_by_play,
    CASE
        WHEN events.game_id IS NULL THEN FALSE
        WHEN games.home_score IS NULL THEN FALSE
        WHEN games.away_score IS NULL THEN FALSE
        WHEN scores.play_by_play_home_score
            != games.home_score THEN FALSE
        WHEN scores.play_by_play_away_score
            != games.away_score THEN FALSE
        ELSE TRUE
    END AS final_score_matches,
    CASE
        WHEN events.game_id IS NULL
            THEN 'missing'
        WHEN games.home_score IS NULL
            OR games.away_score IS NULL
            THEN 'incomplete'
        WHEN scores.play_by_play_home_score
            = games.home_score
            AND scores.play_by_play_away_score
            = games.away_score
            THEN 'complete'
        ELSE 'incomplete'
    END AS coverage_status
FROM raw.games AS games
LEFT JOIN event_summaries AS events
    ON games.game_id = events.game_id
LEFT JOIN final_scores AS scores
    ON games.game_id = scores.game_id;


CREATE OR REPLACE VIEW marts.play_by_play_coverage_summary AS
SELECT
    COUNT(*) AS total_games,
    COUNT_IF(coverage_status = 'complete')
        AS complete_games,
    COUNT_IF(coverage_status = 'incomplete')
        AS incomplete_games,
    COUNT_IF(coverage_status = 'missing')
        AS missing_games,
    ROUND(
        100.0
        * COUNT_IF(coverage_status = 'complete')
        / NULLIF(COUNT(*), 0),
        2
    ) AS coverage_percentage
FROM marts.play_by_play_coverage;


CREATE OR REPLACE VIEW marts.team_play_by_play_coverage AS
WITH game_teams AS (
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
    teams.team_id,
    teams.team_abbreviation,
    COUNT(*) AS total_games,
    COUNT_IF(coverage.coverage_status = 'complete')
        AS complete_games,
    COUNT_IF(coverage.coverage_status = 'incomplete')
        AS incomplete_games,
    COUNT_IF(coverage.coverage_status = 'missing')
        AS missing_games,
    ROUND(
        100.0
        * COUNT_IF(coverage.coverage_status = 'complete')
        / NULLIF(COUNT(*), 0),
        2
    ) AS coverage_percentage
FROM game_teams AS teams
INNER JOIN marts.play_by_play_coverage AS coverage
    ON teams.game_id = coverage.game_id
GROUP BY
    teams.team_id,
    teams.team_abbreviation;