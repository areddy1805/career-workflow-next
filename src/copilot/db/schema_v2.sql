-- CareerFlow Application Copilot — SLICE 5 schema (migration v2).
-- Contextual value policy + submitted field values (append-only evidence).
--
-- Directive chain (never violated):
--   GROUND TRUTH -> PROFILE/POSITIONING POLICY -> APPLICATION CONTEXT
--   -> RECOMMENDATION -> USER DECISION -> SUBMITTED VALUE -> OUTCOME
--
-- Ground truth (config/ground_truth.yaml) is NEVER mutated. Submitted
-- values here are immutable evidence: no UPDATE/DELETE; corrections insert
-- a new row with supersedes -> old id.

CREATE TABLE field_value_policies (
    policy_id        TEXT PRIMARY KEY NOT NULL,
    field_intent     TEXT NOT NULL,
    profile_id       TEXT NOT NULL,
    ground_truth_ref TEXT,
    rules_json       TEXT NOT NULL,
    stats_json       TEXT,
    status           TEXT NOT NULL CHECK(status IN ('draft','active','disabled')),
    created_at       TEXT NOT NULL,
    activated_at     TEXT
);

CREATE INDEX idx_fvp_field_profile ON field_value_policies (field_intent, profile_id);

CREATE TABLE application_field_values (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id            TEXT NOT NULL,
    job_id                TEXT NOT NULL,
    field_intent          TEXT NOT NULL,
    recommended_value     TEXT,
    recommendation_source TEXT,
    confidence            REAL,
    user_override         TEXT,
    submitted_value       TEXT NOT NULL,
    outcome               TEXT,
    profile_id            TEXT NOT NULL,
    job_context_json      TEXT,
    created_at            TEXT NOT NULL,
    supersedes            INTEGER
);

-- Idempotency key: (session_id, job_id, field_intent) on PRIMARY submissions.
-- Partial index: corrections (supersedes NOT NULL) insert a new row, so the
-- (session, job, intent) uniqueness applies only to supersedes IS NULL rows.
CREATE UNIQUE INDEX idx_afv_submission_key
    ON application_field_values (session_id, job_id, field_intent)
    WHERE supersedes IS NULL;

-- Learning scan: same (field_intent, profile_id), chronological by id.
CREATE INDEX idx_afv_learning ON application_field_values (field_intent, profile_id, id);
