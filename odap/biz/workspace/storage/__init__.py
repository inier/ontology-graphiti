"""存储模块"""

from .sqlite_storage import SQLiteStorage

# 使用SQLite存储作为默认存储
Storage = SQLiteStorage

__all__ = ["Storage"]