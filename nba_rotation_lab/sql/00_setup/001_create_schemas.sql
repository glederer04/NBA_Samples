CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS metadata.pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    pipeline_name VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL
        CHECK (status IN ('running', 'completed', 'failed')),
    row_count BIGINT,
    message VARCHAR
);