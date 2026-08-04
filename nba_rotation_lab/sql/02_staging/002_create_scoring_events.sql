CREATE OR REPLACE VIEW staging.scoring_events AS
WITH ordered_score_states AS (
    SELECT
        events.game_id,
        events.action_id,
        events.action_number,
        events.period,
        events.clock,
        events.game_elapsed_deciseconds,
        events.team_id,
        events.team_abbreviation,
        events.player_id,
        events.player_name,
        events.action_type,
        events.sub_type,
        events.description,
        events.score_home,
        events.score_away,
        LAG(events.score_home, 1, 0) OVER (
            PARTITION BY events.game_id
            ORDER BY
                events.game_elapsed_deciseconds,
                events.action_number,
                events.action_id
        ) AS previous_home_score,
        LAG(events.score_away, 1, 0) OVER (
            PARTITION BY events.game_id
            ORDER BY
                events.game_elapsed_deciseconds,
                events.action_number,
                events.action_id
        ) AS previous_away_score
    FROM raw.play_by_play_events AS events
    WHERE
        events.score_home IS NOT NULL
        AND events.score_away IS NOT NULL
),

score_changes AS (
    SELECT
        ordered.*,
        ordered.score_home
            - ordered.previous_home_score
            AS home_points,
        ordered.score_away
            - ordered.previous_away_score
            AS away_points
    FROM ordered_score_states AS ordered
)

SELECT
    changes.game_id,
    changes.action_id,
    changes.action_number,
    changes.period,
    changes.clock,
    changes.game_elapsed_deciseconds,
    changes.team_id,
    changes.team_abbreviation,
    changes.player_id,
    changes.player_name,
    changes.action_type,
    changes.sub_type,
    changes.description,
    changes.previous_home_score,
    changes.previous_away_score,
    changes.score_home,
    changes.score_away,
    changes.home_points,
    changes.away_points,
    CASE
        WHEN
            changes.home_points > 0
            AND changes.away_points = 0
            THEN games.home_team_id
        WHEN
            changes.away_points > 0
            AND changes.home_points = 0
            THEN games.away_team_id
    END AS scoring_team_id,
    CASE
        WHEN
            changes.home_points > 0
            AND changes.away_points = 0
            THEN games.home_team_abbreviation
        WHEN
            changes.away_points > 0
            AND changes.home_points = 0
            THEN games.away_team_abbreviation
    END AS scoring_team_abbreviation,
    GREATEST(
        changes.home_points,
        changes.away_points
    ) AS points_scored,
    (
        changes.home_points < 0
        OR changes.away_points < 0
        OR (
            changes.home_points != 0
            AND changes.away_points != 0
        )
    ) AS is_score_correction
FROM score_changes AS changes
INNER JOIN raw.games AS games
    ON changes.game_id = games.game_id
WHERE
    changes.home_points != 0
    OR changes.away_points != 0;