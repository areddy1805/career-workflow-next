"""SQLite connection + bootstrap for copilot.db (CP-0-02, ADR-010).

``open_copilot_db`` is the bootstrap-on-first-use entry point: it connects to
the configured DB path (from ``config/copilot.yaml``), enables WAL, and runs
pending migrations. Every call returns a fresh connection — this is a
single-user local store, no pooling needed (ponytail: add pooling only if a
profile shows connection overhead).
"""

import sqlite3
from pathlib import Path

from src.copilot.config.loader import load_copilot_config
from src.copilot.db.migrate import migrate


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection to ``db_path`` with WAL, FK enforcement, Row rows."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def open_copilot_db() -> sqlite3.Connection:
    """Bootstrap copilot.db on first use: connect + migrate, then return."""
    conn = connect(load_copilot_config().db_path)
    migrate(conn)
    return conn
