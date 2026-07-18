"""Web 爬取存储层"""

from odap.biz.data.web_crawl.storage.sqlite_collection_storage import SQLiteCollectionStorage

Storage = SQLiteCollectionStorage

__all__ = ["SQLiteCollectionStorage", "Storage"]
