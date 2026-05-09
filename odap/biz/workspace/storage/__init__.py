"""存储模块"""

import logging

logger = logging.getLogger("workspace_storage")

from .sqlite_storage import SQLiteStorage

Storage = SQLiteStorage

try:
    from .mongodb_storage import MongoDBStorage
    try:
        _test_client = MongoDBStorage()
        _test_client.client.admin.command('ping')
        Storage = MongoDBStorage
        logger.info("Using MongoDB storage")
    except Exception:
        logger.info("MongoDB unavailable, using SQLite storage")
except ImportError:
    logger.info("MongoDB module not installed, using SQLite storage")

__all__ = ["Storage", "SQLiteStorage"]