"""ActionService 编排层 (T383)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict

execute_action() 流程：
1. 加载 ActionType
2. OPA 权限校验 (write-time check)
3. 拒绝 → 创建 DENIED execution + 写审计 + 返回
4. 通过 → 调用 ActionExecutor → 落库 execution
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..impl import ActionTypeRepositoryImpl, SkillBackedExecutor
from ..interfaces import ActionExecutor, ActionTypeRepository
from ..models import ActionExecution, ActionExecutionStatus, ActionType
from ..storage import SQLiteActionStorage

logger = logging.getLogger(__name__)


class ActionService:
    """Action Type 编排服务"""

    def __init__(
        self,
        repository: ActionTypeRepository = None,
        executor: ActionExecutor = None,
        storage: SQLiteActionStorage = None,
        opa_check: Any = None,
    ):
        self.storage = storage or SQLiteActionStorage()
        self.repository = repository or ActionTypeRepositoryImpl(storage=self.storage)
        self.executor = executor or SkillBackedExecutor()
        self._opa_check = opa_check  # 注入: (action_type, user_context) -> bool

    # ---------- ActionType CRUD ----------

    def create_action_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建 ActionType"""
        try:
            at = self._build_action_type(payload, new_id=True)
            self.repository.save(at)
            return self._action_type_to_dict(at)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": f"create_action_type failed: {exc}"}

    def get_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """获取 ActionType"""
        try:
            at = self.repository.get(action_type_id)
            if not at:
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            return self._action_type_to_dict(at)
        except Exception as exc:
            return {"status": "error", "message": f"get_action_type failed: {exc}"}

    def list_action_types(
        self,
        enabled_only: bool = False,
        object_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出 ActionType；支持 enabled_only / object_type 过滤"""
        try:
            if object_type:
                items = self.repository.list_by_object_type(object_type)
            else:
                items = self.repository.list(enabled_only=enabled_only)
            return {
                "action_types": [self._action_type_to_dict(a) for a in items],
                "count": len(items),
            }
        except Exception as exc:
            return {"status": "error", "message": f"list_action_types failed: {exc}"}

    def update_action_type(
        self, action_type_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新 ActionType（部分字段）"""
        try:
            existing = self.repository.get(action_type_id)
            if not existing:
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            merged = self._merge_action_type(existing, payload)
            self.repository.save(merged)
            return self._action_type_to_dict(merged)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": f"update_action_type failed: {exc}"}

    def delete_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """删除 ActionType"""
        try:
            ok = self.repository.delete(action_type_id)
            if not ok:
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            return {"action_type_id": action_type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_action_type failed: {exc}"}

    # ---------- 执行 ----------

    def execute_action(
        self,
        action_type_id: str,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行 ActionType：OPA 校验 → 调用执行器 → 落库

        OPA 拒绝时仍创建一条 DENIED 状态的 execution 记录，
        便于审计追溯"哪些用户被拒绝了什么操作"。
        """
        try:
            at = self.repository.get(action_type_id)
            if not at:
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}

            if not self._opa_allows(at, user_context):
                denied = self._denied_execution(at, parameters, user_context)
                self.repository.save_execution(denied)
                return self._execution_to_dict(denied)

            execution = self.executor.execute(at, parameters, user_context)
            self.repository.save_execution(execution)
            return self._execution_to_dict(execution)
        except Exception as exc:
            logger.exception("execute_action failed")
            return {"status": "error", "message": f"execute_action failed: {exc}"}

    def list_executions(
        self, action_type_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """列出某 ActionType 的执行历史"""
        try:
            rows = self.repository.list_executions(action_type_id, limit=limit)
            return {
                "executions": [self._execution_to_dict(r) for r in rows],
                "count": len(rows),
            }
        except Exception as exc:
            return {"status": "error", "message": f"list_executions failed: {exc}"}

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """根据 ID 获取 ActionExecution"""
        try:
            row = self.repository.get_execution(execution_id)
            if not row:
                return {"status": "error", "message": f"execution not found: {execution_id}"}
            return self._execution_to_dict(row)
        except Exception as exc:
            return {"status": "error", "message": f"get_execution failed: {exc}"}

    # ---------- 内部工具 ----------

    def _opa_allows(
        self, action_type: ActionType, user_context: Dict[str, Any]
    ) -> bool:
        """调用注入的 OPA 校验；未注入时按"无策略=放行"处理"""
        if self._opa_check is None:
            return True
        try:
            return bool(self._opa_check(action_type, user_context))
        except Exception as exc:
            # OPA 调用异常 → fail-closed (拒绝)
            logger.warning("OPA check raised, fail-closed: %s", exc)
            return False

    def _denied_execution(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """构造 DENIED 状态的 execution"""
        from datetime import datetime
        return ActionExecution(
            action_type_id=action_type.id,
            parameters=parameters,
            status=ActionExecutionStatus.DENIED,
            error_message="OPA permission denied",
            user_id=user_context.get("user_id", "system"),
            workspace_id=user_context.get("ws_id", "default"),
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_ms=0,
        )

    @staticmethod
    def _build_action_type(payload: Dict[str, Any], new_id: bool) -> ActionType:
        """从 payload 构造 ActionType；进行字段校验"""
        name = payload.get("name")
        if not name or not str(name).strip():
            raise ValueError("name is required and must be non-empty")
        if not payload.get("linked_skill_id"):
            raise ValueError("linked_skill_id is required")
        action_type_id = None if new_id else payload.get("id")
        return ActionType(
            id=action_type_id or payload.get("id") or _new_id(),
            name=name,
            description=payload.get("description", ""),
            object_types=payload.get("object_types", []) or [],
            parameters=payload.get("parameters", {}) or {},
            return_type=payload.get("return_type", "void") or "void",
            side_effects=payload.get("side_effects", []) or [],
            linked_skill_id=payload.get("linked_skill_id"),
            opa_policy_ref=payload.get("opa_policy_ref", "") or "",
            enabled=bool(payload.get("enabled", True)),
        )

    @staticmethod
    def _merge_action_type(
        existing: ActionType, payload: Dict[str, Any]
    ) -> ActionType:
        """合并更新字段；不传则保留原值"""
        merged_payload = {
            "id": existing.id,
            "name": payload.get("name", existing.name),
            "description": payload.get("description", existing.description),
            "object_types": payload.get("object_types", existing.object_types),
            "parameters": payload.get("parameters", existing.parameters),
            "return_type": payload.get("return_type", existing.return_type),
            "side_effects": payload.get("side_effects", existing.side_effects),
            "linked_skill_id": payload.get("linked_skill_id", existing.linked_skill_id),
            "opa_policy_ref": payload.get("opa_policy_ref", existing.opa_policy_ref),
            "enabled": payload.get("enabled", existing.enabled),
        }
        return ActionService._build_action_type(merged_payload, new_id=False)

    @staticmethod
    def _action_type_to_dict(at: ActionType) -> Dict[str, Any]:
        """ActionType → 扁平 dict"""
        return {
            "id": at.id,
            "name": at.name,
            "description": at.description,
            "object_types": at.object_types,
            "parameters": at.parameters,
            "return_type": at.return_type,
            "side_effects": at.side_effects,
            "linked_skill_id": at.linked_skill_id,
            "opa_policy_ref": at.opa_policy_ref,
            "enabled": at.enabled,
            "created_at": at.created_at.isoformat(),
            "updated_at": at.updated_at.isoformat(),
        }

    @staticmethod
    def _execution_to_dict(execution: ActionExecution) -> Dict[str, Any]:
        """ActionExecution → 扁平 dict"""
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


def _new_id() -> str:
    """生成 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())
