CREATE TABLE IF NOT EXISTS raw.teams (
    team_id BIGINT PRIMARY KEY,
    abbreviation VARCHAR NOT NULL,
    team_name VARCHAR NOT NULL,
    city VARCHAR,
    state VARCHAR,
    year_founded INTEGER,
    source_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.players (
    player_id BIGINT PRIMARY KEY,
    full_name VARCHAR NOT NULL,
    first_name VARCHAR,
    last_name VARCHAR,
    is_active BOOLEAN,
    source_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.games (
    game_id VARCHAR PRIMARY KEY,
    season_id VARCHAR,
    game_date DATE,
    season_type VARCHAR,
    home_team_id BIGINT,
    away_team_id BIGINT,
    home_team_abbreviation VARCHAR,
    away_team_abbreviation VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    game_status VARCHAR,
    source_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);