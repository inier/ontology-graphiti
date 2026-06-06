"""Action Type - SQLite 持久化层"""
from .sqlite_action_storage import SQLiteActionStorage

Storage = SQLiteActionStorage

__all__ = ["Storage", "SQLiteActionStorage"]
