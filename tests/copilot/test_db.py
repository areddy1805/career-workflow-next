"""Unit tests for CP-0-02: copilot.db schema + migration runner."""

import sqlite3

import pytest

from src.copilot.db.db import connect, open_copilot_db
from src.copilot.db.migrate import (
    SCHEMA_VERSION,
    MigrationError,
    apply_sql,
    migrate,
)

# Frozen schema, 02_ARCHITECTURE.md §7.8 — table -> exact column set.
FROZEN_TABLES = {
    "copilot_opportunities": {
        "id", "fingerprint", "source", "source_ref", "data_json",
        "provenance_json", "pipeline_job_id", "status_view", "created_at",
        "updated_at", "synced_from",
    },
    "copilot_sources": {
        "opportunity_id", "source", "raw_ref", "fetched_at", "raw_hash"
    },
    "copilot_briefs": {
        "opportunity_id", "brief_json", "generated_at", "model_used",
        "sections_version",
    },
    "copilot_answers": {
        "question_fp", "profile_id", "canonical_label", "category", "source",
        "semantic_answer", "serialized_answer", "confidence", "status", "reason",
        "use_count", "last_used_at", "outcome_quality",
    },
    "copilot_sessions": {
        "session_id", "opportunity_id", "state", "profile_id", "resume_id",
        "brief_snapshot_json", "answers_snapshot_json", "created_at",
        "updated_at", "submitted_at", "outcome", "outcome_at",
    },
    "copilot_session_events": {
        "session_id", "seq", "event_type", "occurred_at", "payload_json"
    },
    "copilot_browser_actions": {
        "id", "session_id", "occurred_at", "action", "target", "field_id",
        "resolution_json", "audit_note",
    },
    "copilot_learning_outcomes": {
        "id", "opportunity_id", "session_id", "job_id", "provider_id",
        "ats_type", "resume_profile", "outcome", "timestamps_json", "created_at",
    },
    "copilot_learning_weights": {"key", "value_json", "updated_at", "source"},
    "copilot_events": {
        "event_id", "event_type", "aggregate_id", "aggregate_type",
        "occurred_at", "payload_json", "trace_id",
    },
    # SLICE 5 (migration v2): contextual value policy + submitted values.
    "field_value_policies": {
        "policy_id", "field_intent", "profile_id", "ground_truth_ref",
        "rules_json", "stats_json", "status", "created_at", "activated_at",
    },
    "application_field_values": {
        "id", "session_id", "job_id", "field_intent", "recommended_value",
        "recommendation_source", "confidence", "user_override",
        "submitted_value", "outcome", "profile_id", "job_context_json",
        "created_at", "supersedes",
    },
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r["name"] for r in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nested" / "copilot.db"  # parent dir does not exist yet


def test_fresh_db_creates_all_frozen_tables(db_path):
    with connect(db_path) as conn:
        migrate(conn)
        assert _tables(conn) == set(FROZEN_TABLES)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_frozen_schema_columns_match_section_7_8(db_path):
    conn = connect(db_path)
    migrate(conn)
    for table, expected_columns in FROZEN_TABLES.items():
        assert _columns(conn, table) == expected_columns, table
    conn.close()


def test_wal_enabled(db_path):
    conn = connect(db_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_connection_defaults(db_path):
    conn = connect(db_path)
    assert conn.row_factory is sqlite3.Row
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_migrate_idempotent(db_path):
    conn = connect(db_path)
    migrate(conn)
    migrate(conn)  # second run must be a no-op
    assert _tables(conn) == set(FROZEN_TABLES)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


def test_version_gate_skips_migrations_when_already_applied(db_path):
    conn = connect(db_path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    migrate(conn)  # no tables exist, but version gate must skip
    assert _tables(conn) == set()
    conn.close()


def test_broken_schema_rolls_back_completely(db_path):
    conn = connect(db_path)
    broken = (
        "CREATE TABLE t1 (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE t2 (id INTEGER PRIMARY KEY,);\n"  # trailing comma -> error
    )
    with pytest.raises(MigrationError):
        apply_sql(conn, broken)
    # Transactional DDL: not even t1 survives the rollback.
    assert _tables(conn) == set()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()


def test_incomplete_statement_rejected(db_path):
    conn = connect(db_path)
    with pytest.raises(MigrationError):
        apply_sql(conn, "CREATE TABLE t1 (id INTEGER PRIMARY KEY")
    conn.close()


def test_bootstrap_creates_parent_dir_and_migrates(db_path, tmp_path, monkeypatch):
    cfg_path = tmp_path / "copilot.yaml"
    cfg_path.write_text(f"copilot:\n  db_path: \"{db_path}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg_path))
    with open_copilot_db() as conn:
        assert db_path.exists()
        assert _tables(conn) == set(FROZEN_TABLES)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
