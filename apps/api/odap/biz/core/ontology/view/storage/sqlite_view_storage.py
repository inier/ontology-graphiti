"""Object View - SQLite 存储层 (T407)

两张表：
- object_views: 视图元数据
- view_permissions: 视图角色权限（UNIQUE(view_id, role)）

AGENTS.md 规则 8：每次 connect/close，无连接池。
AGENTS.md 规则 5：JSON 字段用 TEXT 存储，datetime 用 ISO 字符串。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


DEFAULT_VIEW_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_VIEW_DB_PATH = os.path.join(DEFAULT_VIEW_DB_DIR, "object_view.db")


class SQLiteViewStorage:
    """视图与权限的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_VIEW_DB_DIR, exist_ok=True)
            db_path = DEFAULT_VIEW_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化表结构（幂等）"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_views_table(conn)
            self._create_permissions_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_views_table(conn):
        """object_views 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS object_views (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                base_type_id TEXT NOT NULL,
                role TEXT NOT NULL,
                projected_properties TEXT DEFAULT '[]',
                filters TEXT DEFAULT '{}',
                row_limit INTEGER DEFAULT 100,
                sort_order TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                created_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_permissions_table(conn):
        """view_permissions 表（UNIQUE(view_id, role)）"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS view_permissions (
                id TEXT PRIMARY KEY,
                view_id TEXT NOT NULL,
                role TEXT NOT NULL,
                can_export INTEGER DEFAULT 0,
                can_share INTEGER DEFAULT 0,
                redaction_rules TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(view_id, role)
            )
            """
        )

    @staticmethod
    def _create_indexes(conn):
        """创建查询索引"""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_object_views_base_type ON object_views(base_type_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_object_views_role ON object_views(role)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_view_permissions_view ON view_permissions(view_id)"
        )

    # ---------- object_views CRUD ----------

    def save_view(self, view: Dict[str, Any]) -> None:
        """保存或更新视图（upsert）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO object_views
                (id, name, description, base_type_id, role, projected_properties,
                 filters, row_limit, sort_order, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    view.get("id", ""),
                    view.get("name", ""),
                    view.get("description", ""),
                    view.get("base_type_id", ""),
                    view.get("role", ""),
                    json.dumps(view.get("projected_properties", []), ensure_ascii=False),
                    json.dumps(view.get("filters", {}), ensure_ascii=False),
                    int(view.get("row_limit", 100)),
                    json.dumps(view.get("sort_order", []), ensure_ascii=False),
                    1 if view.get("enabled", True) else 0,
                    view.get("created_by", "system"),
                    view.get("created_at", ""),
                    view.get("updated_at", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_view(self, view_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取视图；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM object_views WHERE id = ?", (view_id,)
            )
            row = cursor.fetchone()
            return self._row_to_view(dict(row)) if row else None
        finally:
            conn.close()

    def list_views(self) -> List[Dict[str, Any]]:
        """列出所有视图"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM object_views ORDER BY created_at DESC"
            )
            return [self._row_to_view(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_views_by_base_type(self, base_type_id: str) -> List[Dict[str, Any]]:
        """按 base_type_id 过滤视图"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM object_views WHERE base_type_id = ? ORDER BY created_at DESC",
                (base_type_id,),
            )
            return [self._row_to_view(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_views_by_role(self, role: str) -> List[Dict[str, Any]]:
        """按角色名过滤视图"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM object_views WHERE role = ? ORDER BY created_at DESC",
                (role,),
            )
            return [self._row_to_view(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_view(self, view_id: str) -> bool:
        """删除视图；返回是否成功（同时级联删除其权限）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM view_permissions WHERE view_id = ?", (view_id,)
            )
            cursor = conn.execute(
                "DELETE FROM object_views WHERE id = ?", (view_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ---------- view_permissions CRUD ----------

    def save_permission(self, perm: Dict[str, Any]) -> None:
        """保存或更新权限（upsert；UNIQUE(view_id, role)）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO view_permissions
                (id, view_id, role, can_export, can_share, redaction_rules, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    perm.get("id", ""),
                    perm.get("view_id", ""),
                    perm.get("role", ""),
                    1 if perm.get("can_export", False) else 0,
                    1 if perm.get("can_share", False) else 0,
                    json.dumps(perm.get("redaction_rules", {}), ensure_ascii=False),
                    perm.get("created_at", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_permissions(self, view_id: str) -> List[Dict[str, Any]]:
        """列出视图的全部权限记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM view_permissions WHERE view_id = ? ORDER BY created_at DESC",
                (view_id,),
            )
            return [self._row_to_permission(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_permission(self, perm_id: str) -> bool:
        """删除权限；返回是否成功"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM view_permissions WHERE id = ?", (perm_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ---------- 私有工具 ----------

    @staticmethod
    def _row_to_view(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite 行 → view dict；JSON 字段反序列化"""
        row = dict(row)
        row["projected_properties"] = _safe_json_loads(
            row.get("projected_properties"), []
        )
        row["filters"] = _safe_json_loads(row.get("filters"), {})
        row["sort_order"] = _safe_json_loads(row.get("sort_order"), [])
        row["enabled"] = bool(row.get("enabled", 1))
        return row

    @staticmethod
    def _row_to_permission(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite 行 → permission dict"""
        row = dict(row)
        row["redaction_rules"] = _safe_json_loads(
            row.get("redaction_rules"), {}
        )
        row["can_export"] = bool(row.get("can_export", 0))
        row["can_share"] = bool(row.get("can_share", 0))
        return row


def _safe_json_loads(value, default):
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
