import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class CacheBackend(ABC):
    @abstractmethod
    def get(self, table: str, key_col: str, key_val: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def set(self, table: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute(self, query: str, params: Tuple = ()) -> Any:
        pass


class SQLiteBackend(CacheBackend):
    def __init__(self, db_path: str | Path, schema_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path = Path(schema_path)
        
        # We use a thread-local object since sqlite3 connections cannot easily 
        # be shared across threads by default without check_same_thread=False
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self.db_path, 
                timeout=30.0, 
                isolation_level=None  # autocommit mode
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found at {self.schema_path}")
            
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            schema_script = f.read()
            
        conn = self._get_conn()
        conn.executescript(schema_script)

    def get(self, table: str, key_col: str, key_val: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.execute(f"SELECT * FROM {table} WHERE {key_col} = ?", (key_val,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_multi(self, table: str, key_col: str, key_vals: List[str]) -> List[Dict[str, Any]]:
        if not key_vals:
            return []
        conn = self._get_conn()
        placeholders = ",".join(["?"] * len(key_vals))
        cursor = conn.execute(f"SELECT * FROM {table} WHERE {key_col} IN ({placeholders})", tuple(key_vals))
        return [dict(row) for row in cursor.fetchall()]

    def set(self, table: str, data: Dict[str, Any]) -> None:
        conn = self._get_conn()
        keys = list(data.keys())
        columns = ", ".join(keys)
        placeholders = ", ".join(["?"] * len(keys))
        values = tuple(data[k] for k in keys)
        
        query = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        conn.execute(query, values)

    def execute(self, query: str, params: Tuple = ()) -> Any:
        conn = self._get_conn()
        cursor = conn.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            return [dict(row) for row in cursor.fetchall()]
        return cursor.rowcount
