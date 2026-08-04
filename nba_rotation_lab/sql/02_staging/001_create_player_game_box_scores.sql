CREATE OR REPLACE VIEW staging.player_game_box_scores AS
SELECT
    box_scores.game_id,
    games.game_date,
    games.season_id,
    games.season_type,
    box_scores.team_id,
    box_scores.team_abbreviation,
    box_scores.player_id,
    box_scores.player_name,
    box_scores.position,
    box_scores.minutes,
    box_scores.starter,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN 'home'
        WHEN box_scores.team_id = games.away_team_id
            THEN 'away'
        ELSE 'unknown'
    END AS game_location,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN games.away_team_id
        WHEN box_scores.team_id = games.away_team_id
            THEN games.home_team_id
    END AS opponent_team_id,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN games.away_team_abbreviation
        WHEN box_scores.team_id = games.away_team_id
            THEN games.home_team_abbreviation
    END AS opponent_team_abbreviation,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN games.home_score
        WHEN box_scores.team_id = games.away_team_id
            THEN games.away_score
    END AS team_score,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN games.away_score
        WHEN box_scores.team_id = games.away_team_id
            THEN games.home_score
    END AS opponent_score,
    CASE
        WHEN box_scores.team_id = games.home_team_id
            THEN games.home_score > games.away_score
        WHEN box_scores.team_id = games.away_team_id
            THEN games.away_score > games.home_score
    END AS won_game,
    box_scores.field_goals_made,
    box_scores.field_goals_attempted,
    box_scores.field_goal_percentage,
    box_scores.three_pointers_made,
    box_scores.three_pointers_attempted,
    box_scores.three_point_percentage,
    box_scores.free_throws_made,
    box_scores.free_throws_attempted,
    box_scores.free_throw_percentage,
    box_scores.offensive_rebounds,
    box_scores.defensive_rebounds,
    box_scores.total_rebounds,
    box_scores.assists,
    box_scores.steals,
    box_scores.blocks,
    box_scores.turnovers,
    box_scores.personal_fouls,
    box_scores.points,
    box_scores.plus_minus
FROM raw.player_box_scores AS box_scores
INNER JOIN raw.games AS games
    ON box_scores.game_id = games.game_id
WHERE
    box_scores.did_not_play = FALSE
    AND box_scores.minutes > 0;