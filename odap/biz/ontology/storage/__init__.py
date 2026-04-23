"""数据摄入存储模块"""

from .mongodb_storage import MongoDBStorage
from .sqlite_ingest_storage import SQLiteIngestStorage

# 使用 MongoDB 存储作为默认存储
Storage = MongoDBStorage

__all__ = ['Storage', 'MongoDBStorage', 'SQLiteIngestStorage']