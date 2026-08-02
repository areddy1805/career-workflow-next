"""Copilot persistence layer (copilot.db)."""

from src.copilot.db.db import connect, open_copilot_db

__all__ = ["connect", "open_copilot_db"]
