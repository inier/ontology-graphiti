"""存储模块"""

from .sqlite_ingest_storage import SQLiteIngestStorage

Storage = SQLiteIngestStorage

__all__ = ["Storage", "SQLiteIngestStorage"]
