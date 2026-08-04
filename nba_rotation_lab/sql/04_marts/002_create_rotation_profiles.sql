CREATE OR REPLACE VIEW marts.player_rotation_profiles AS
SELECT
    team_id,
    team_abbreviation,
    player_id,
    player_name,
    COUNT(DISTINCT game_id) AS games_played,
    SUM(
        CASE
            WHEN starter THEN 1
            ELSE 0
        END
    ) AS games_started,
    ROUND(
        100.0
        * SUM(
            CASE
                WHEN starter THEN 1
                ELSE 0
            END
        )
        / NULLIF(COUNT(DISTINCT game_id), 0),
        2
    ) AS start_percentage,
    ROUND(SUM(minutes), 2) AS total_minutes,
    ROUND(AVG(minutes), 2) AS average_minutes,
    ROUND(
        COALESCE(STDDEV_SAMP(minutes), 0),
        2
    ) AS minutes_standard_deviation,
    ROUND(AVG(points), 2) AS average_points,
    ROUND(AVG(total_rebounds), 2) AS average_rebounds,
    ROUND(AVG(assists), 2) AS average_assists,
    ROUND(AVG(turnovers), 2) AS average_turnovers,
    ROUND(AVG(plus_minus), 2) AS average_plus_minus,
    ROUND(
        100.0
        * SUM(field_goals_made)
        / NULLIF(SUM(field_goals_attempted), 0),
        2
    ) AS field_goal_percentage,
    ROUND(
        100.0
        * SUM(three_pointers_made)
        / NULLIF(SUM(three_pointers_attempted), 0),
        2
    ) AS three_point_percentage,
    ROUND(
        100.0
        * SUM(free_throws_made)
        / NULLIF(SUM(free_throws_attempted), 0),
        2
    ) AS free_throw_percentage,
    ROUND(
        36.0 * SUM(points)
        / NULLIF(SUM(minutes), 0),
        2
    ) AS points_per_36,
    ROUND(
        36.0 * SUM(total_rebounds)
        / NULLIF(SUM(minutes), 0),
        2
    ) AS rebounds_per_36,
    ROUND(
        36.0 * SUM(assists)
        / NULLIF(SUM(minutes), 0),
        2
    ) AS assists_per_36,
    ROUND(
        36.0 * SUM(turnovers)
        / NULLIF(SUM(minutes), 0),
        2
    ) AS turnovers_per_36,
    CASE
        WHEN AVG(minutes) >= 30
            THEN 'core'
        WHEN AVG(minutes) >= 20
            THEN 'rotation'
        WHEN AVG(minutes) >= 10
            THEN 'depth'
        ELSE 'limited'
    END AS rotation_role,
    CASE
        WHEN COUNT(DISTINCT game_id) >= 10
            THEN 'established'
        WHEN COUNT(DISTINCT game_id) >= 5
            THEN 'directional'
        ELSE 'preliminary'
    END AS sample_size_status,
    MAX(game_date) AS latest_game_date
FROM staging.player_game_box_scores
GROUP BY
    team_id,
    team_abbreviation,
    player_id,
    player_name;


CREATE OR REPLACE VIEW marts.team_rotation_profiles AS
WITH team_game_stats AS (
    SELECT
        team_id,
        team_abbreviation,
        game_id,
        COUNT(DISTINCT player_id) AS players_used,
        SUM(minutes) AS team_minutes,
        SUM(
            CASE
                WHEN starter THEN minutes
                ELSE 0
            END
        ) AS starter_minutes,
        SUM(points) AS total_points,
        SUM(
            CASE
                WHEN starter = FALSE THEN points
                ELSE 0
            END
        ) AS bench_points
    FROM staging.player_game_box_scores
    GROUP BY
        team_id,
        team_abbreviation,
        game_id
),

team_summary AS (
    SELECT
        team_id,
        team_abbreviation,
        COUNT(DISTINCT game_id) AS covered_games,
        ROUND(AVG(players_used), 2)
            AS average_players_used,
        ROUND(AVG(team_minutes), 2)
            AS average_team_minutes,
        ROUND(
            100.0 * SUM(starter_minutes)
            / NULLIF(SUM(team_minutes), 0),
            2
        ) AS starter_minutes_percentage,
        ROUND(
            100.0 * SUM(bench_points)
            / NULLIF(SUM(total_points), 0),
            2
        ) AS bench_scoring_percentage
    FROM team_game_stats
    GROUP BY
        team_id,
        team_abbreviation
),

player_minutes AS (
    SELECT
        team_id,
        team_abbreviation,
        player_id,
        SUM(minutes) AS player_minutes
    FROM staging.player_game_box_scores
    GROUP BY
        team_id,
        team_abbreviation,
        player_id
),

ranked_player_minutes AS (
    SELECT
        team_id,
        team_abbreviation,
        player_id,
        player_minutes,
        ROW_NUMBER() OVER (
            PARTITION BY team_id
            ORDER BY
                player_minutes DESC,
                player_id
        ) AS minutes_rank
    FROM player_minutes
),

minutes_concentration AS (
    SELECT
        team_id,
        team_abbreviation,
        ROUND(
            100.0
            * SUM(
                CASE
                    WHEN minutes_rank <= 5
                        THEN player_minutes
                    ELSE 0
                END
            )
            / NULLIF(SUM(player_minutes), 0),
            2
        ) AS top_five_minutes_percentage
    FROM ranked_player_minutes
    GROUP BY
        team_id,
        team_abbreviation
)

SELECT
    summary.team_id,
    summary.team_abbreviation,
    summary.covered_games,
    (
        SELECT COUNT(DISTINCT player_id)
        FROM staging.player_game_box_scores AS players
        WHERE players.team_id = summary.team_id
    ) AS players_used,
    summary.average_players_used,
    summary.average_team_minutes,
    summary.starter_minutes_percentage,
    summary.bench_scoring_percentage,
    concentration.top_five_minutes_percentage,
    CASE
        WHEN summary.average_players_used <= 9
            THEN 'tight'
        WHEN summary.average_players_used <= 11
            THEN 'standard'
        ELSE 'deep'
    END AS rotation_style,
    CASE
        WHEN summary.covered_games >= 10
            THEN 'established'
        WHEN summary.covered_games >= 5
            THEN 'directional'
        ELSE 'preliminary'
    END AS sample_size_status
FROM team_summary AS summary
INNER JOIN minutes_concentration AS concentration
    ON summary.team_id = concentration.team_id;