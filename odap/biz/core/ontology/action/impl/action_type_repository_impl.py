"""ActionTypeRepositoryImpl (T381)

实现 ActionTypeRepository 抽象基类的 8 个方法，
依赖 SQLiteActionStorage 持久化，Domain Object ↔ dict 转换在这里完成。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..interfaces import ActionTypeRepository
from ..models import ActionExecution, ActionExecutionStatus, ActionType
from ..storage import SQLiteActionStorage


class ActionTypeRepositoryImpl(ActionTypeRepository):
    """ActionType 仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteActionStorage = None):
        self.storage = storage or SQLiteActionStorage()

    # ---------- ActionType CRUD ----------

    def save(self, action_type: ActionType) -> ActionType:
        """保存或更新 ActionType（upsert）"""
        action_type.updated_at = datetime.now()
        self.storage.save_action_type(self._to_dict(action_type))
        return action_type

    def get(self, action_type_id: str) -> Optional[ActionType]:
        """根据 ID 获取 ActionType"""
        row = self.storage.get_action_type(action_type_id)
        return self._from_dict(row) if row else None

    def list(self, enabled_only: bool = False) -> List[ActionType]:
        """列出所有 ActionType"""
        rows = self.storage.list_action_types(enabled_only=enabled_only)
        return [self._from_dict(r) for r in rows]

    def list_by_object_type(self, type_id: str) -> List[ActionType]:
        """按适用 ObjectType 过滤 ActionType"""
        rows = self.storage.list_action_types_by_object_type(type_id)
        return [self._from_dict(r) for r in rows]

    def delete(self, action_type_id: str) -> bool:
        """删除 ActionType；返回是否成功"""
        return self.storage.delete_action_type(action_type_id)

    # ---------- ActionExecution ----------

    def save_execution(self, execution: ActionExecution) -> ActionExecution:
        """保存 ActionExecution（upsert）"""
        self.storage.save_execution(self._execution_to_dict(execution))
        return execution

    def get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        """根据 ID 获取 ActionExecution"""
        row = self.storage.get_execution(execution_id)
        return self._dict_to_execution(row) if row else None

    def list_executions(self, action_type_id: str, limit: int = 50) -> List[ActionExecution]:
        """列出某 ActionType 的最近 N 次执行"""
        rows = self.storage.list_executions(action_type_id, limit=limit)
        return [self._dict_to_execution(r) for r in rows]

    # ---------- 内部工具 ----------

    @staticmethod
    def _to_dict(action_type: ActionType) -> dict:
        """ActionType → 持久化 dict"""
        return {
            "id": action_type.id,
            "name": action_type.name,
            "description": action_type.description,
            "object_types": action_type.object_types,
            "parameters": action_type.parameters,
            "return_type": action_type.return_type,
            "side_effects": action_type.side_effects,
            "linked_skill_id": action_type.linked_skill_id,
            "opa_policy_ref": action_type.opa_policy_ref,
            "enabled": action_type.enabled,
            "created_at": action_type.created_at.isoformat(),
            "updated_at": action_type.updated_at.isoformat(),
        }

    @staticmethod
    def _from_dict(row: dict) -> ActionType:
        """持久化 dict → ActionType"""
        return ActionType(
            id=row.get("id", ""),
            name=row.get("name", ""),
            description=row.get("description", ""),
            object_types=row.get("object_types", []) or [],
            parameters=row.get("parameters", {}) or {},
            return_type=row.get("return_type", "void"),
            side_effects=row.get("side_effects", []) or [],
            linked_skill_id=row.get("linked_skill_id"),
            opa_policy_ref=row.get("opa_policy_ref", ""),
            enabled=bool(row.get("enabled", True)),
            created_at=_parse_dt(row.get("created_at")),
            updated_at=_parse_dt(row.get("updated_at")),
        )

    @staticmethod
    def _execution_to_dict(execution: ActionExecution) -> dict:
        """ActionExecution → 持久化 dict"""
        finished = execution.finished_at
        return {
            "id": execution.id,
            "action_type_id": execution.action_type_id,
            "parameters": execution.parameters,
            "result": execution.result,
            "status": execution.status.value,
            "error_message": execution.error_message,
            "audit_record_id": execution.audit_record_id,
            "user_id": execution.user_id,
            "workspace_id": execution.workspace_id,
            "started_at": execution.started_at.isoformat(),
            "finished_at": finished.isoformat() if finished else None,
            "duration_ms": execution.duration_ms,
        }

    @staticmethod
    def _dict_to_execution(row: dict) -> ActionExecution:
        """持久化 dict → ActionExecution"""
        finished_raw = row.get("finished_at")
        finished = _parse_dt(finished_raw) if finished_raw else None
        return ActionExecution(
            id=row.get("id", ""),
            action_type_id=row.get("action_type_id", ""),
            parameters=row.get("parameters", {}) or {},
            result=row.get("result", {}) or {},
            status=ActionExecutionStatus(row.get("status", "pending")),
            error_message=row.get("error_message", "") or "",
            audit_record_id=row.get("audit_record_id"),
            user_id=row.get("user_id", "system"),
            workspace_id=row.get("workspace_id", "default"),
            started_at=_parse_dt(row.get("started_at")),
            finished_at=finished,
            duration_ms=row.get("duration_ms"),
        )


def _parse_dt(value):
    """从 ISO 字符串解析 datetime；失败时回退到 now()"""
    if not value:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now()
