"""Candidate Store Storage SQLite 实现别名导出（AGENTS.md §3.1 biz 模块结构）。"""

from __future__ import annotations

from .sqlite_candidate_storage import SQLiteCandidateStorage

# AGENTS.md §C SQLite 存储规则：storage/__init__.py 必须别名导出 Storage = SQLiteXxxStorage
Storage = SQLiteCandidateStorage

__all__ = ["SQLiteCandidateStorage", "Storage"]
