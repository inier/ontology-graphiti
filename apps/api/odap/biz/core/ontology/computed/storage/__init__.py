"""Computed Property - SQLite 持久化层"""
from .sqlite_computed_storage import SQLiteComputedStorage

Storage = SQLiteComputedStorage

__all__ = ["Storage", "SQLiteComputedStorage"]
