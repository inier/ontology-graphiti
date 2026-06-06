"""SQLite 持久化模块 (T347, T353)"""
from .sqlite_branch_storage import SQLiteBranchStorage

Storage = SQLiteBranchStorage

__all__ = ["SQLiteBranchStorage", "Storage"]
