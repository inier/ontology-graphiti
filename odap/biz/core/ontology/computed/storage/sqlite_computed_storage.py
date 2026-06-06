"""SQLite Computed Storage (T396)

三张表：
- computed_properties: ComputedProperty 元数据
- materialization_jobs: 物化任务历史
- materialized_values: 物化结果缓存 (property_id + instance_id 唯一)

AGENTS.md 规则 8：每次 connect/close，无连接池。
AGENTS.md 规则 5：JSON 字段用 TEXT 存储，datetime 用 ISO 字符串。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


DEFAULT_COMPUTED_DB_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.getcwd(), "data")
)
DEFAULT_COMPUTED_DB_PATH = os.path.join(
    DEFAULT_COMPUTED_DB_DIR, "computed.db"
)


def _safe_json_loads(value: Any, default: Any) -> Any:
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (int, float, bool)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _parse_dt_iso(value: Any):
    """从 ISO 字符串解析 datetime；失败时返回 None"""
    if not value:
        return None
    from datetime import datetime
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class SQLiteComputedStorage:
    """Computed Property 的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_COMPUTED_DB_DIR, exist_ok=True)
            db_path = DEFAULT_COMPUTED_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化表结构（幂等）"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_properties_table(conn)
            self._create_jobs_table(conn)
            self._create_values_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_properties_table(conn) -> None:
        """computed_properties 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS computed_properties (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                target_type_id TEXT NOT NULL,
                expression TEXT NOT NULL,
                dependencies TEXT DEFAULT '[]',
                materialization TEXT NOT NULL,
                return_type TEXT DEFAULT 'any',
                description TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_jobs_table(conn) -> None:
        """materialization_jobs 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS materialization_jobs (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                processed_count INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                triggered_by TEXT DEFAULT 'manual',
                mode TEXT DEFAULT 'incremental'
            )
            """
        )

    @staticmethod
    def _create_values_table(conn) -> None:
        """materialized_values 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS materialized_values (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                instance_id TEXT NOT NULL,
                value TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                UNIQUE(property_id, instance_id)
            )
            """
        )

    @staticmethod
    def _create_indexes(conn) -> None:
        """创建查询索引"""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_props_target "
            "ON computed_properties(target_type_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_props_enabled "
            "ON computed_properties(enabled)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_property "
            "ON materialization_jobs(property_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_started "
            "ON materialization_jobs(started_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_values_property "
            "ON materialized_values(property_id)"
        )

    # ---------- computed_properties CRUD ----------

    def save_property(self, prop: Dict[str, Any]) -> None:
        """保存或更新 ComputedProperty（upsert）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO computed_properties
                (id, name, target_type_id, expression, dependencies,
                 materialization, return_type, description, enabled,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prop.get("id", ""),
                    prop.get("name", ""),
                    prop.get("target_type_id", ""),
                    prop.get("expression", ""),
                    json.dumps(
                        prop.get("dependencies", []), ensure_ascii=False
                    ),
                    prop.get("materialization", "incremental"),
                    prop.get("return_type", "any"),
                    prop.get("description", ""),
                    1 if prop.get("enabled", True) else 0,
                    prop.get("created_at", ""),
                    prop.get("updated_at", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_property(self, prop_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 ComputedProperty；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM computed_properties WHERE id = ?", (prop_id,)
            )
            row = cursor.fetchone()
            return self._row_to_property(dict(row)) if row else None
        finally:
            conn.close()

    def list_properties(
        self,
        target_type_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """列出 ComputedProperty；可按 target_type / enabled 过滤"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM computed_properties"
            clauses: List[str] = []
            params: List[Any] = []
            if target_type_id:
                clauses.append("target_type_id = ?")
                params.append(target_type_id)
            if enabled_only:
                clauses.append("enabled = 1")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY created_at DESC"
            cursor = conn.execute(sql, tuple(params))
            return [self._row_to_property(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_property(self, prop_id: str) -> bool:
        """删除 ComputedProperty；返回是否成功"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM computed_properties WHERE id = ?", (prop_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ---------- materialization_jobs CRUD ----------

    def save_job(self, job: Dict[str, Any]) -> None:
        """保存 MaterializationJob（upsert）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO materialization_jobs
                (id, property_id, status, started_at, finished_at,
                 processed_count, error_message, triggered_by, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.get("id", ""),
                    job.get("property_id", ""),
                    job.get("status", "pending"),
                    job.get("started_at", ""),
                    job.get("finished_at"),
                    job.get("processed_count", 0),
                    job.get("error_message", ""),
                    job.get("triggered_by", "manual"),
                    job.get("mode", "incremental"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 MaterializationJob；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM materialization_jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            return self._row_to_job(dict(row)) if row else None
        finally:
            conn.close()

    def list_jobs(
        self, property_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出某 ComputedProperty 的最近 N 个任务"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM materialization_jobs WHERE property_id = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (property_id, max(1, int(limit))),
            )
            return [self._row_to_job(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ---------- materialized_values CRUD ----------

    def save_materialized_value(
        self,
        property_id: str,
        instance_id: str,
        value: Any,
        computed_at_iso: str,
    ) -> None:
        """保存物化值（upsert by (property_id, instance_id)）"""
        import uuid
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO materialized_values
                (id, property_id, instance_id, value, computed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    property_id,
                    instance_id,
                    json.dumps(value, ensure_ascii=False, default=str),
                    computed_at_iso,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_materialized_value(
        self, property_id: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取物化值；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM materialized_values "
                "WHERE property_id = ? AND instance_id = ?",
                (property_id, instance_id),
            )
            row = cursor.fetchone()
            return self._row_to_value(dict(row)) if row else None
        finally:
            conn.close()

    def list_materialized_values(
        self, property_id: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出某 ComputedProperty 的所有物化值"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM materialized_values WHERE property_id = ? "
                "ORDER BY computed_at DESC LIMIT ?",
                (property_id, max(1, int(limit))),
            )
            return [self._row_to_value(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_materialized_values(self, property_id: str) -> int:
        """删除某 ComputedProperty 的全部物化值；返回删除条数"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM materialized_values WHERE property_id = ?",
                (property_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ---------- 私有工具 ----------

    @staticmethod
    def _row_to_property(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；JSON 字段反序列化"""
        row = dict(row)
        row["dependencies"] = _safe_json_loads(row.get("dependencies"), [])
        row["enabled"] = bool(row.get("enabled", 0))
        return row

    @staticmethod
    def _row_to_job(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict"""
        row = dict(row)
        return row

    @staticmethod
    def _row_to_value(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；value 字段 JSON 反序列化"""
        row = dict(row)
        row["value"] = _safe_json_loads(row.get("value"), None)
        return row


__all__ = ["SQLiteComputedStorage"]
