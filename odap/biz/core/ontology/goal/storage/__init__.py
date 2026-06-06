"""OntoFlow Goal - SQLite 持久化层"""
from .sqlite_goal_storage import SQLiteGoalStorage

Storage = SQLiteGoalStorage

__all__ = ["Storage", "SQLiteGoalStorage"]
