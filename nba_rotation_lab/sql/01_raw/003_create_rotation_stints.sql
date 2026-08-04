CREATE TABLE IF NOT EXISTS raw.rotation_stints (
    game_id VARCHAR NOT NULL,
    team_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    stint_number INTEGER NOT NULL,
    team_location VARCHAR NOT NULL
        CHECK (team_location IN ('home', 'away')),
    team_city VARCHAR,
    team_name VARCHAR,
    player_name VARCHAR NOT NULL,
    period INTEGER NOT NULL,
    in_time_deciseconds BIGINT NOT NULL,
    out_time_deciseconds BIGINT NOT NULL,
    in_time_seconds DOUBLE NOT NULL,
    out_time_seconds DOUBLE NOT NULL,
    duration_seconds DOUBLE NOT NULL,
    player_points INTEGER,
    point_differential DOUBLE,
    usage_percentage DOUBLE,
    source_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        game_id,
        team_id,
        player_id,
        stint_number
    ),
    CHECK (out_time_deciseconds > in_time_deciseconds),
    CHECK (duration_seconds > 0)
);