"""SQLite 持久化模块"""
from .sqlite_conflict_storage import SQLiteConflictStorage

Storage = SQLiteConflictStorage

__all__ = ["SQLiteConflictStorage", "Storage"]
