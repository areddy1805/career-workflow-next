"""Migration runner for copilot.db (CP-0-02).

Schema versions are tracked with ``PRAGMA user_version`` (sqlite built-in), so
the frozen table set from 02_ARCHITECTURE.md §7.8 is not polluted by a
bookkeeping table. Migrations run transactionally: each statement is applied
inside one transaction, so a broken migration rolls back completely and
leaves no partial schema and an unchanged version.
"""

import sqlite3

from src.copilot.exceptions import CopilotError

SCHEMA_VERSION = 1


class MigrationError(CopilotError):
    """Raised when a migration fails to apply; the transaction is rolled back."""


def _load_schema_sql() -> str:
    """Return the body of ``schema.sql`` (migration v1)."""
    from pathlib import Path

    return (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def _split_statements(sql: str) -> list[str]:
    """Split SQL text into complete statements (stdlib-aware of quotes)."""
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer)
            buffer = ""
    if buffer.strip():
        raise MigrationError(f"incomplete SQL statement: {buffer!r}")
    return statements


def apply_sql(conn: sqlite3.Connection, sql: str) -> None:
    """Execute plain DDL statements transactionally; roll back on any failure.

    DDL inside an explicit ``BEGIN`` is fully transactional in sqlite (the
    sqlite3 module's implicit transactions only cover DML and would let each
    CREATE TABLE auto-commit). Exposed for tests: a failing statement leaves
    no partial schema behind.
    """
    try:
        conn.execute("BEGIN")
        for statement in _split_statements(sql):
            conn.execute(statement)
    except sqlite3.Error as e:
        conn.execute("ROLLBACK")
        raise MigrationError(f"migration failed (rolled back): {e}") from e
    else:
        conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations; no-op when already at SCHEMA_VERSION."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return
    apply_sql(conn, _load_schema_sql())
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
