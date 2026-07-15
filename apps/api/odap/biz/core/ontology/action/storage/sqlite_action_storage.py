"""Action Type - SQLite 存储层 (T380)

两张表：
- action_types: ActionType 元数据
- action_executions: ActionExecution 执行历史

AGENTS.md 规则 8：每次 connect/close，无连接池。
AGENTS.md 规则 5：JSON 字段用 TEXT 存储，datetime 用 ISO 字符串。

审计（双通道）：
- 写操作 CRUD（save_action_type / delete_action_type / save_execution）：
  优先 storage_audit(service="agent_action") → 回退 log_audit → 回退 logger.warning
- 读操作（get / list）：不记审计（上层 service 已记）
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional


DEFAULT_ACTION_DB_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.getcwd(), "data")
)
DEFAULT_ACTION_DB_PATH = os.path.join(DEFAULT_ACTION_DB_DIR, "action_type.db")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 存储层审计辅助：双通道，只记写操作 CRUD，不打断业务
# ---------------------------------------------------------------------------

def _storage_audit(
    action: str,
    *,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: str = "",
    latency_ms: Optional[int] = None,
) -> None:
    """写操作双通道审计：storage_audit → log_audit → logger.warning"""
    _details = dict(details or {})
    if latency_ms is not None:
        _details.setdefault("latency_ms", latency_ms)
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            resource=resource,
            details=_details,
            service="agent_action",
            result_status=result_status,
            result_message=result_message,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed: {e}")

    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource,
            user="system",
            service="agent_action",
            details=_details,
            result_status=result_status,
            result_message=result_message,
            duration_ms=latency_ms,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (log_audit fallback): {e}")


class SQLiteActionStorage:
    """ActionType / ActionExecution 的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_ACTION_DB_DIR, exist_ok=True)
            db_path = DEFAULT_ACTION_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化表结构（幂等）"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_action_types_table(conn)
            self._create_action_executions_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_action_types_table(conn) -> None:
        """action_types 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_types (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                object_types TEXT DEFAULT '[]',
                parameters TEXT DEFAULT '{}',
                return_type TEXT DEFAULT 'void',
                side_effects TEXT DEFAULT '[]',
                linked_skill_id TEXT,
                opa_policy_ref TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_action_executions_table(conn) -> None:
        """action_executions 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_executions (
                id TEXT PRIMARY KEY,
                action_type_id TEXT NOT NULL,
                parameters TEXT DEFAULT '{}',
                result TEXT DEFAULT '{}',
                status TEXT NOT NULL,
                error_message TEXT DEFAULT '',
                audit_record_id TEXT,
                user_id TEXT DEFAULT 'system',
                workspace_id TEXT DEFAULT 'default',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms INTEGER
            )
            """
        )

    @staticmethod
    def _create_indexes(conn) -> None:
        """创建 3 个查询索引"""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_types_enabled "
            "ON action_types(enabled)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_executions_type "
            "ON action_executions(action_type_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_executions_started "
            "ON action_executions(started_at)"
        )

    # ---------- action_types CRUD ----------

    def save_action_type(self, action_type: Dict[str, Any]) -> None:
        """保存或更新 ActionType（upsert） - 写操作双通道审计"""
        start = time.perf_counter()
        action_type_id = action_type.get("id", "") or "unknown"
        name = action_type.get("name", "")
        is_update = False
        try:
            # 判断是否为 update：先查是否存在
            pre_existing = self.get_action_type(action_type_id)
            is_update = pre_existing is not None
        except Exception:
            is_update = False

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO action_types
                    (id, name, description, object_types, parameters, return_type,
                     side_effects, linked_skill_id, opa_policy_ref, enabled,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_type.get("id", ""),
                        action_type.get("name", ""),
                        action_type.get("description", ""),
                        json.dumps(
                            action_type.get("object_types", []), ensure_ascii=False
                        ),
                        json.dumps(
                            action_type.get("parameters", {}), ensure_ascii=False
                        ),
                        action_type.get("return_type", "void"),
                        json.dumps(
                            action_type.get("side_effects", []), ensure_ascii=False
                        ),
                        action_type.get("linked_skill_id"),
                        action_type.get("opa_policy_ref", ""),
                        1 if action_type.get("enabled", True) else 0,
                        action_type.get("created_at", ""),
                        action_type.get("updated_at", ""),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                audit_action = (
                    "storage_action_type_update_success"
                    if is_update
                    else "storage_action_type_create_success"
                )
                _storage_audit(
                    audit_action,
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "name": name,
                        "linked_skill_id": action_type.get("linked_skill_id", ""),
                        "enabled": bool(action_type.get("enabled", True)),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                audit_action = (
                    "storage_action_type_update_failed"
                    if is_update
                    else "storage_action_type_create_failed"
                )
                _storage_audit(
                    audit_action,
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "name": name,
                    },
                    result_status="failure",
                    result_message=str(exc)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 ActionType；不存在返回 None（读操作不记审计，上层记）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM action_types WHERE id = ?", (action_type_id,)
            )
            row = cursor.fetchone()
            return self._row_to_action_type(dict(row)) if row else None
        finally:
            conn.close()

    def list_action_types(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列出所有 ActionType（读操作不记审计）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            if enabled_only:
                cursor = conn.execute(
                    "SELECT * FROM action_types WHERE enabled = 1 "
                    "ORDER BY created_at DESC"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM action_types ORDER BY created_at DESC"
                )
            return [self._row_to_action_type(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_action_types_by_object_type(
        self, object_type: str
    ) -> List[Dict[str, Any]]:
        """按 object_types 过滤 (LIKE 匹配，因为是 JSON 数组字符串)（读不记审计）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            pattern = f'%"{object_type}"%'
            cursor = conn.execute(
                "SELECT * FROM action_types WHERE object_types LIKE ? "
                "ORDER BY created_at DESC",
                (pattern,),
            )
            return [self._row_to_action_type(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_action_type(self, action_type_id: str) -> bool:
        """删除 ActionType；返回是否存在并删除（写操作双通道审计）"""
        start = time.perf_counter()
        rowcount = 0
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM action_types WHERE id = ?", (action_type_id,)
                )
                rowcount = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
            latency_ms = int((time.perf_counter() - start) * 1000)
            if rowcount > 0:
                try:
                    _storage_audit(
                        "storage_action_type_delete_success",
                        resource=action_type_id,
                        details={"action_type_id": action_type_id},
                        result_status="success",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
            else:
                try:
                    _storage_audit(
                        "storage_action_type_delete_miss",
                        resource=action_type_id,
                        details={"action_type_id": action_type_id},
                        result_status="success",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
            return rowcount > 0
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _storage_audit(
                    "storage_action_type_delete_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=str(exc)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    # ---------- action_executions CRUD ----------

    def save_execution(self, execution: Dict[str, Any]) -> None:
        """保存 ActionExecution（upsert）- 写操作双通道审计"""
        start = time.perf_counter()
        execution_id = execution.get("id", "") or "unknown"
        action_type_id = execution.get("action_type_id", "")
        status = execution.get("status", "unknown")

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO action_executions
                    (id, action_type_id, parameters, result, status, error_message,
                     audit_record_id, user_id, workspace_id, started_at,
                     finished_at, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution.get("id", ""),
                        execution.get("action_type_id", ""),
                        json.dumps(execution.get("parameters", {}), ensure_ascii=False),
                        json.dumps(execution.get("result", {}), ensure_ascii=False),
                        execution.get("status", "pending"),
                        execution.get("error_message", ""),
                        execution.get("audit_record_id"),
                        execution.get("user_id", "system"),
                        execution.get("workspace_id", "default"),
                        execution.get("started_at", ""),
                        execution.get("finished_at"),
                        execution.get("duration_ms"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _storage_audit(
                    "storage_execution_save_success",
                    resource=execution_id,
                    details={
                        "execution_id": execution_id,
                        "action_type_id": action_type_id,
                        "status": str(status),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _storage_audit(
                    "storage_execution_save_failed",
                    resource=execution_id,
                    details={
                        "execution_id": execution_id,
                        "action_type_id": action_type_id,
                    },
                    result_status="failure",
                    result_message=str(exc)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            raise

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 ActionExecution（读操作不记审计）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM action_executions WHERE id = ?", (execution_id,)
            )
            row = cursor.fetchone()
            return self._row_to_execution(dict(row)) if row else None
        finally:
            conn.close()

    def list_executions(
        self, action_type_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出某 ActionType 的最近 N 次执行（读操作不记审计）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM action_executions WHERE action_type_id = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (action_type_id, max(1, int(limit))),
            )
            return [self._row_to_execution(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ---------- 私有工具 ----------

    @staticmethod
    def _row_to_action_type(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；JSON 字段反序列化"""
        row = dict(row)
        row["object_types"] = _safe_json_loads(row.get("object_types"), [])
        row["parameters"] = _safe_json_loads(row.get("parameters"), {})
        row["side_effects"] = _safe_json_loads(row.get("side_effects"), [])
        row["enabled"] = bool(row.get("enabled", 0))
        return row

    @staticmethod
    def _row_to_execution(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；JSON 字段反序列化"""
        row = dict(row)
        row["parameters"] = _safe_json_loads(row.get("parameters"), {})
        row["result"] = _safe_json_loads(row.get("result"), {})
        return row


def _safe_json_loads(value: Any, default: Any) -> Any:
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
