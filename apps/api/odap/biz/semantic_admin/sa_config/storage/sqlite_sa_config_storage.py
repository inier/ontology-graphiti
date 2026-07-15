"""SQLite storage for sa_config 表 — 语义管理台动态配置持久化层。

DDL 中使用唯一约束 UNIQUE(scope, config_key) 保证同一分组下 key 不重复。
每次操作 sqlite3.connect → close，符合 SQLite 无连接池规则（AGENTS.md §B）。
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

from odap.biz.semantic_admin.sa_config.models import SaConfigEntry


def _resolve_db_path(db_path: Optional[str]) -> str:
    if db_path:
        return db_path
    return os.path.join(
        os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
        "semantic_admin.db",
    )


_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS sa_config (
    id                  TEXT PRIMARY KEY,
    scope               TEXT NOT NULL,
    config_key          TEXT NOT NULL,
    config_value_json   TEXT NOT NULL DEFAULT '{}',
    updated_by          TEXT NOT NULL DEFAULT 'system',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE(scope, config_key)
);
CREATE INDEX IF NOT EXISTS idx_sa_config_scope ON sa_config(scope);
"""


class SQLiteSaConfigStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = _resolve_db_path(db_path)
        self._init_db()

    # ------------------------------------------------------------------
    # init
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_TABLE_DDL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def save_config(self, entry: SaConfigEntry) -> SaConfigEntry:
        """Upsert：同 (scope, config_key) 时覆盖 value、updated_by、updated_at。"""
        row = entry.to_row()
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.row_factory = self._row_factory
            existing = cur.execute(
                "SELECT id FROM sa_config WHERE scope = ? AND config_key = ?",
                (row["scope"], row["config_key"]),
            ).fetchone()
            if existing:
                row["id"] = existing["id"]
                cur.execute(
                    """UPDATE sa_config
                       SET config_value_json = ?, updated_by = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        row["config_value_json"],
                        row["updated_by"],
                        row["updated_at"],
                        row["id"],
                    ),
                )
            else:
                cur.execute(
                    """INSERT INTO sa_config
                       (id, scope, config_key, config_value_json, updated_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["id"],
                        row["scope"],
                        row["config_key"],
                        row["config_value_json"],
                        row["updated_by"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            conn.commit()
            fetched = cur.execute(
                "SELECT * FROM sa_config WHERE id = ?", (row["id"],)
            ).fetchone()
            return SaConfigEntry.from_row(fetched)
        finally:
            conn.close()

    def get_config(self, scope: str, config_key: str) -> Optional[SaConfigEntry]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.row_factory = self._row_factory
            row = cur.execute(
                "SELECT * FROM sa_config WHERE scope = ? AND config_key = ?",
                (scope, config_key),
            ).fetchone()
            return SaConfigEntry.from_row(row) if row else None
        finally:
            conn.close()

    def get_value(
        self, scope: str, config_key: str
    ) -> Optional[Dict[str, Any]]:
        entry = self.get_config(scope, config_key)
        return entry.config_value if entry else None

    def list_configs(self, scope: Optional[str] = None) -> List[SaConfigEntry]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.row_factory = self._row_factory
            if scope:
                rows = cur.execute(
                    "SELECT * FROM sa_config WHERE scope = ? ORDER BY config_key",
                    (scope,),
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT * FROM sa_config ORDER BY scope, config_key"
                ).fetchall()
            return [SaConfigEntry.from_row(r) for r in rows]
        finally:
            conn.close()

    def delete_config(self, scope: str, config_key: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM sa_config WHERE scope = ? AND config_key = ?",
                (scope, config_key),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


__all__ = ["SQLiteSaConfigStorage"]
