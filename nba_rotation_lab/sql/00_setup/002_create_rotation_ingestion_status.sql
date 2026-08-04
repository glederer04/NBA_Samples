CREATE TABLE IF NOT EXISTS metadata.rotation_ingestion_status (
    game_id VARCHAR PRIMARY KEY,
    status VARCHAR NOT NULL,
    error_message VARCHAR,
    last_attempted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('unavailable'))
);
