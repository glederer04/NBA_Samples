-- Narrow materialized identities; each valid five-player interval has ten trios.
CREATE TABLE IF NOT EXISTS intermediate.trio_interval_membership (
    game_id VARCHAR, team_id BIGINT, interval_number BIGINT,
    trio_key VARCHAR, player_one BIGINT, player_two BIGINT, player_three BIGINT,
    PRIMARY KEY (team_id, game_id, interval_number, trio_key)
);
CREATE TABLE IF NOT EXISTS marts.trio_game_performance (
    game_id VARCHAR, team_id BIGINT, team_abbreviation VARCHAR, game_date DATE,
    trio_key VARCHAR, seconds DOUBLE, points_for BIGINT, points_against BIGINT,
    boundary_points BIGINT, intervals BIGINT,
    PRIMARY KEY (team_id, game_id, trio_key)
);
