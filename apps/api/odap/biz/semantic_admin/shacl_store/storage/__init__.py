"""SHACL Store - Storage 别名导出。

AGENTS.md §C SQLite 存储规则：storage/__init__.py 必须别名导出 Storage = SQLiteXxxStorage。
"""

from __future__ import annotations

from .sqlite_shacl_storage import SQLiteShaclStorage

Storage = SQLiteShaclStorage

__all__ = ["SQLiteShaclStorage", "Storage"]
