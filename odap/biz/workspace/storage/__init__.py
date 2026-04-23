"""存储模块"""

from .mongodb_storage import MongoDBStorage
from .sqlite_storage import SQLiteStorage

# 使用 MongoDB 存储作为默认存储
Storage = MongoDBStorage

__all__ = ["Storage", "MongoDBStorage", "SQLiteStorage"]