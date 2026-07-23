-- src/cache/schema.sql

CREATE TABLE IF NOT EXISTS llm_cache (
    fingerprint TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    provider TEXT NOT NULL,
    job_id TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    parsed_response TEXT,
    model TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    tokens INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    fingerprint TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detail_fetch_cache (
    fingerprint TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    provider TEXT NOT NULL,
    job_id TEXT NOT NULL,
    content TEXT NOT NULL,
    etag TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS http_cache (
    fingerprint TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    url TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    headers_json TEXT,
    content BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);


CREATE INDEX IF NOT EXISTS idx_llm_cache_job_id ON llm_cache(job_id);
CREATE INDEX IF NOT EXISTS idx_detail_fetch_expires ON detail_fetch_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_http_cache_expires ON http_cache(expires_at);
