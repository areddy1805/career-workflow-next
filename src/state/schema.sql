-- src/state/schema.sql

CREATE TABLE IF NOT EXISTS job_state (
    provider TEXT NOT NULL,
    provider_job_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    fingerprint TEXT,
    
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    times_seen INTEGER DEFAULT 1,
    
    current_status TEXT,
    last_status TEXT,
    last_score INTEGER,
    last_rank INTEGER,
    
    applied BOOLEAN DEFAULT 0,
    ignored BOOLEAN DEFAULT 0,
    manual_override TEXT,
    
    application_run_id TEXT,
    last_application_attempt TIMESTAMP,
    application_method TEXT,
    
    pipeline_version TEXT,
    decision_version TEXT,
    last_ai_fingerprint TEXT,
    
    PRIMARY KEY (provider, provider_job_id)
);
