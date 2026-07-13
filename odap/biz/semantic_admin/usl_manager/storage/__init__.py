"""USL Manager - Storage 别名导出。

AGENTS.md §B SQLite 存储规则：Storage = SQLiteXxxStorage。
"""

from __future__ import annotations

from .sqlite_usl_storage import SQLiteUslStorage

Storage = SQLiteUslStorage

__all__ = ["SQLiteUslStorage", "Storage"]
