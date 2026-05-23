"""存储模块"""

from .sqlite_storage import SQLiteStorage

Storage = SQLiteStorage

__all__ = ["Storage", "SQLiteStorage"]
