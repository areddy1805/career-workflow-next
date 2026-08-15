-- CareerFlow Application Copilot — copilot.db schema v1 (CP-0-02).
-- Implements the frozen persistence schema 02_ARCHITECTURE.md §7.8.
-- This file is the migration body for schema version 1.
-- Do not edit the frozen contract; changes require an ADR.

CREATE TABLE copilot_opportunities (
    id               TEXT PRIMARY KEY NOT NULL,
    fingerprint      TEXT UNIQUE NOT NULL,
    source           TEXT NOT NULL,
    source_ref       TEXT,
    data_json        TEXT NOT NULL,
    provenance_json  TEXT NOT NULL,
    pipeline_job_id  TEXT,
    status_view      TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    synced_from      TEXT
);

CREATE TABLE copilot_sources (
    opportunity_id  TEXT NOT NULL,
    source          TEXT NOT NULL,
    raw_ref         TEXT,
    fetched_at      TEXT,
    raw_hash        TEXT,
    PRIMARY KEY (opportunity_id, source)
);

CREATE TABLE copilot_briefs (
    opportunity_id   TEXT PRIMARY KEY NOT NULL,
    brief_json       TEXT NOT NULL,
    generated_at     TEXT NOT NULL,
    model_used       TEXT,
    sections_version TEXT
);

CREATE TABLE copilot_answers (
    question_fp       TEXT NOT NULL,
    profile_id        TEXT NOT NULL,
    canonical_label   TEXT,
    category          TEXT,
    source            TEXT,
    semantic_answer   TEXT,
    serialized_answer TEXT,
    confidence        REAL,
    status            TEXT NOT NULL,
    reason            TEXT,
    use_count         INTEGER NOT NULL DEFAULT 0,
    last_used_at      TEXT,
    outcome_quality   REAL,
    PRIMARY KEY (question_fp, profile_id)
);

-- Documented indexes (06_ANSWER_BANK.md §8).
CREATE INDEX idx_copilot_answers_status ON copilot_answers (status);
CREATE INDEX idx_copilot_answers_last_used ON copilot_answers (last_used_at);

CREATE TABLE copilot_sessions (
    session_id            TEXT PRIMARY KEY NOT NULL,
    opportunity_id        TEXT NOT NULL,
    state                 TEXT NOT NULL,
    profile_id            TEXT,
    resume_id             TEXT,
    brief_snapshot_json   TEXT,
    answers_snapshot_json TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    submitted_at          TEXT,
    outcome               TEXT,
    outcome_at            TEXT
);

CREATE TABLE copilot_session_events (
    session_id   TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    event_type   TEXT NOT NULL,
    occurred_at  TEXT NOT NULL,
    payload_json TEXT,
    PRIMARY KEY (session_id, seq)
);

CREATE TABLE copilot_browser_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    occurred_at     TEXT NOT NULL,
    action          TEXT NOT NULL,
    target          TEXT,
    field_id        TEXT,
    resolution_json TEXT,
    audit_note      TEXT
);

CREATE TABLE copilot_learning_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT,
    session_id      TEXT UNIQUE,
    job_id          TEXT,
    provider_id     TEXT,
    ats_type        TEXT,
    resume_profile  TEXT,
    outcome         TEXT,
    timestamps_json TEXT,
    created_at      TEXT
);

CREATE TABLE copilot_learning_weights (
    key        TEXT PRIMARY KEY NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source     TEXT
);

CREATE TABLE copilot_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type     TEXT NOT NULL,
    aggregate_id   TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    occurred_at    TEXT NOT NULL,
    payload_json   TEXT,
    trace_id       TEXT
);
