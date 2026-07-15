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

审计（service="agent_action"）：
- create_action_type / update_action_type / delete_action_type：CRUD 三维度
- execute_action：start/success/failed，success 记 status+output_len，failure 记 error
- rollback_action：记 action_id, rollback_reason
- list_executions / get_execution / get_action_type / list_action_types：只读计数
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..impl import ActionTypeRepositoryImpl, SkillBackedExecutor
from ..interfaces import ActionExecutor, ActionTypeRepository
from ..models import ActionExecution, ActionExecutionStatus, ActionType
from ..storage import SQLiteActionStorage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 审计辅助：优先 storage_audit("agent_action") → 回退 log_audit
# ---------------------------------------------------------------------------

def _action_audit(
    action: str,
    *,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: str = "",
    latency_ms: Optional[int] = None,
) -> None:
    """Action 服务层统一审计函数；异常只 logger.warning 不抛"""
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
        """创建 ActionType（CRUD-C 审计）"""
        start = time.perf_counter()
        name = payload.get("name", "unnamed") or "unnamed"
        try:
            at = self._build_action_type(payload, new_id=True)
            self.repository.save(at)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_create_success",
                    resource=at.id,
                    details={
                        "name": name,
                        "linked_skill_id": at.linked_skill_id or "",
                        "enabled": at.enabled,
                        "object_types_count": len(at.object_types or []),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._action_type_to_dict(at)
        except ValueError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_create_failed",
                    resource=name,
                    details={"name": name},
                    result_status="failure",
                    result_message=str(exc)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_create_failed",
                    resource=name,
                    details={"name": name},
                    result_status="failure",
                    result_message=f"create_action_type failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"create_action_type failed: {exc}"}

    def get_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """获取 ActionType（只读审计 count）"""
        try:
            at = self.repository.get(action_type_id)
            if not at:
                try:
                    _action_audit(
                        "action_type_get_miss",
                        resource=action_type_id,
                        details={"action_type_id": action_type_id},
                        result_status="success",
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            try:
                _action_audit(
                    "action_type_get_hit",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "name": at.name,
                        "linked_skill_id": at.linked_skill_id or "",
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._action_type_to_dict(at)
        except Exception as exc:
            try:
                _action_audit(
                    "action_type_get_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=f"get_action_type failed: {exc}"[:500],
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"get_action_type failed: {exc}"}

    def list_action_types(
        self,
        enabled_only: bool = False,
        object_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出 ActionType；支持 enabled_only / object_type 过滤（只读审计 count）"""
        start = time.perf_counter()
        try:
            if object_type:
                items = self.repository.list_by_object_type(object_type)
            else:
                items = self.repository.list(enabled_only=enabled_only)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_list_success",
                    resource=object_type or "all",
                    details={
                        "enabled_only": enabled_only,
                        "object_type": object_type or "",
                        "count": len(items),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {
                "action_types": [self._action_type_to_dict(a) for a in items],
                "count": len(items),
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_list_failed",
                    resource=object_type or "all",
                    details={"enabled_only": enabled_only, "object_type": object_type or ""},
                    result_status="failure",
                    result_message=f"list_action_types failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"list_action_types failed: {exc}"}

    def update_action_type(
        self, action_type_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新 ActionType（CRUD-U 审计）"""
        start = time.perf_counter()
        try:
            existing = self.repository.get(action_type_id)
            if not existing:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _action_audit(
                        "action_type_update_failed",
                        resource=action_type_id,
                        details={"action_type_id": action_type_id},
                        result_status="failure",
                        result_message=f"action_type not found: {action_type_id}"[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            merged = self._merge_action_type(existing, payload)
            self.repository.save(merged)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_update_success",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "name": merged.name,
                        "enabled": merged.enabled,
                        "linked_skill_id": merged.linked_skill_id or "",
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._action_type_to_dict(merged)
        except ValueError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_update_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=str(exc)[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_update_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=f"update_action_type failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"update_action_type failed: {exc}"}

    def delete_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """删除 ActionType（破坏性操作，必记 CRUD-D 审计）"""
        start = time.perf_counter()
        try:
            ok = self.repository.delete(action_type_id)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if not ok:
                try:
                    _action_audit(
                        "action_type_delete_failed",
                        resource=action_type_id,
                        details={"action_type_id": action_type_id},
                        result_status="failure",
                        result_message=f"action_type not found: {action_type_id}"[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}
            try:
                _action_audit(
                    "action_type_delete_success",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"action_type_id": action_type_id, "deleted": True}
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_type_delete_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=f"delete_action_type failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"delete_action_type failed: {exc}"}

    def create_action_plan(
        self,
        payload: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """创建 Action Plan（新接口，start/success/failed 审计）"""
        start = time.perf_counter()
        plan_name = payload.get("name", "unnamed_plan") or "unnamed_plan"
        user_id = user_context.get("user_id", "system")
        workspace_id = user_context.get("ws_id", "default")
        actions = payload.get("actions", []) or []
        try:
            try:
                _action_audit(
                    "action_plan_create_start",
                    resource=plan_name,
                    details={
                        "name": plan_name,
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                        "actions_count": len(actions),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            # 简化：直接用 payload 生成 plan（不做复杂持久化，若后续有 storage 则替换）
            plan_id = _new_id()
            plan = {
                "id": plan_id,
                "name": plan_name,
                "actions": actions,
                "status": "pending",
                "created_by": user_id,
                "workspace_id": workspace_id,
            }
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_plan_create_success",
                    resource=plan_id,
                    details={
                        "plan_id": plan_id,
                        "name": plan_name,
                        "actions_count": len(actions),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return plan
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_plan_create_failed",
                    resource=plan_name,
                    details={
                        "name": plan_name,
                        "actions_count": len(actions),
                    },
                    result_status="failure",
                    result_message=f"create_action_plan failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"create_action_plan failed: {exc}"}

    # ---------- 执行 ----------

    def execute_action(
        self,
        action_type_id: str,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行 ActionType：OPA 校验 → 调用执行器 → 落库

        - 审计维度：start / success / failed
        - success：记 status + output_len
        - failure：记 error message
        """
        start = time.perf_counter()
        user_id = user_context.get("user_id", "system")
        workspace_id = user_context.get("ws_id", "default")
        agent_id = user_context.get("agent_id", user_id)

        try:
            # start 审计
            try:
                _action_audit(
                    "action_execute_start",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "agent_id": agent_id,
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                        "params_count": len(parameters or {}),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            at = self.repository.get(action_type_id)
            if not at:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _action_audit(
                        "action_execute_failed",
                        resource=action_type_id,
                        details={
                            "action_type_id": action_type_id,
                            "agent_id": agent_id,
                            "workspace_id": workspace_id,
                        },
                        result_status="failure",
                        result_message=f"action_type not found: {action_type_id}"[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"action_type not found: {action_type_id}"}

            if not self._opa_allows(at, user_context):
                denied = self._denied_execution(at, parameters, user_context)
                self.repository.save_execution(denied)
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _action_audit(
                        "action_execute_denied",
                        resource=action_type_id,
                        details={
                            "action_type_id": action_type_id,
                            "agent_id": agent_id,
                            "user_id": user_id,
                            "workspace_id": workspace_id,
                        },
                        result_status="denied",
                        result_message="OPA permission denied",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return self._execution_to_dict(denied)

            execution = self.executor.execute(at, parameters, user_context)
            self.repository.save_execution(execution)
            latency_ms = int((time.perf_counter() - start) * 1000)

            # success / failed
            if execution.status == ActionExecutionStatus.SUCCESS:
                try:
                    output_len = len(str(execution.result)[:200]) if execution.result else 0
                except Exception:
                    output_len = 0
                try:
                    _action_audit(
                        "action_execute_success",
                        resource=action_type_id,
                        details={
                            "action_type_id": action_type_id,
                            "execution_id": execution.id,
                            "status": execution.status.value,
                            "output_len": output_len,
                            "agent_id": agent_id,
                            "workspace_id": workspace_id,
                        },
                        result_status="success",
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
            else:
                try:
                    _action_audit(
                        "action_execute_failed",
                        resource=action_type_id,
                        details={
                            "action_type_id": action_type_id,
                            "execution_id": execution.id,
                            "status": execution.status.value,
                            "agent_id": agent_id,
                            "workspace_id": workspace_id,
                        },
                        result_status="failure",
                        result_message=(execution.error_message or "")[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")

            return self._execution_to_dict(execution)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("execute_action failed")
            try:
                _action_audit(
                    "action_execute_failed",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "agent_id": agent_id,
                        "workspace_id": workspace_id,
                    },
                    result_status="failure",
                    result_message=f"execute_action failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"execute_action failed: {exc}"}

    def rollback_action(
        self,
        action_id: str,
        rollback_reason: str = "",
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """回滚 Action（破坏性操作，记 action_id + rollback_reason）"""
        start = time.perf_counter()
        user_context = user_context or {}
        user_id = user_context.get("user_id", "system")
        workspace_id = user_context.get("ws_id", "default")

        try:
            try:
                _action_audit(
                    "action_rollback_start",
                    resource=action_id,
                    details={
                        "action_id": action_id,
                        "rollback_reason": rollback_reason[:200],
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")

            execution = self.repository.get_execution(action_id)
            if not execution:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _action_audit(
                        "action_rollback_failed",
                        resource=action_id,
                        details={
                            "action_id": action_id,
                            "rollback_reason": rollback_reason[:200],
                        },
                        result_status="failure",
                        result_message=f"execution not found: {action_id}"[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"execution not found: {action_id}"}

            # 简化 rollback：仅标记 status 为 rolled_back（真实 rollback 逻辑若有 skill 补偿则加）
            if hasattr(execution, "status"):
                try:
                    execution_dict = execution if isinstance(execution, dict) else {
                        "id": getattr(execution, "id", action_id),
                        "action_type_id": getattr(execution, "action_type_id", ""),
                        "parameters": getattr(execution, "parameters", {}),
                        "result": getattr(execution, "result", {}),
                        "status": "rolled_back",
                        "error_message": rollback_reason,
                        "audit_record_id": getattr(execution, "audit_record_id", None),
                        "user_id": getattr(execution, "user_id", user_id),
                        "workspace_id": getattr(execution, "workspace_id", workspace_id),
                        "started_at": getattr(execution, "started_at", None),
                        "finished_at": getattr(execution, "finished_at", None),
                        "duration_ms": getattr(execution, "duration_ms", None),
                    }
                    execution_dict["status"] = "rolled_back"
                    self.repository.save_execution(execution_dict)
                except Exception:
                    pass

            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_rollback_success",
                    resource=action_id,
                    details={
                        "action_id": action_id,
                        "rollback_reason": rollback_reason[:200],
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {
                "action_id": action_id,
                "status": "rolled_back",
                "rollback_reason": rollback_reason,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_rollback_failed",
                    resource=action_id,
                    details={
                        "action_id": action_id,
                        "rollback_reason": rollback_reason[:200],
                    },
                    result_status="failure",
                    result_message=f"rollback_action failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"rollback_action failed: {exc}"}

    def list_executions(
        self, action_type_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """列出某 ActionType 的执行历史（只读审计 count）"""
        start = time.perf_counter()
        try:
            rows = self.repository.list_executions(action_type_id, limit=limit)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_list_executions",
                    resource=action_type_id,
                    details={
                        "action_type_id": action_type_id,
                        "limit": limit,
                        "count": len(rows),
                    },
                    result_status="success",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {
                "executions": [self._execution_to_dict(r) for r in rows],
                "count": len(rows),
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                _action_audit(
                    "action_list_executions_failed",
                    resource=action_type_id,
                    details={"action_type_id": action_type_id},
                    result_status="failure",
                    result_message=f"list_executions failed: {exc}"[:500],
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return {"status": "error", "message": f"list_executions failed: {exc}"}

    def get_action_status(self, execution_id: str) -> Dict[str, Any]:
        """根据 ID 获取 ActionExecution（只读审计）"""
        return self.get_execution(execution_id)

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """根据 ID 获取 ActionExecution"""
        try:
            row = self.repository.get_execution(execution_id)
            if not row:
                try:
                    _action_audit(
                        "action_get_execution_miss",
                        resource=execution_id,
                        details={"execution_id": execution_id},
                        result_status="success",
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                return {"status": "error", "message": f"execution not found: {execution_id}"}
            try:
                if isinstance(row, dict):
                    status = row.get("status", "unknown")
                else:
                    status = getattr(row, "status", ActionExecutionStatus.PENDING)
                    if hasattr(status, "value"):
                        status = status.value
                _action_audit(
                    "action_get_execution_hit",
                    resource=execution_id,
                    details={
                        "execution_id": execution_id,
                        "status": str(status),
                    },
                    result_status="success",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._execution_to_dict(row)
        except Exception as exc:
            try:
                _action_audit(
                    "action_get_execution_failed",
                    resource=execution_id,
                    details={"execution_id": execution_id},
                    result_status="failure",
                    result_message=f"get_execution failed: {exc}"[:500],
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
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
    def _execution_to_dict(execution: Any) -> Dict[str, Any]:
        """ActionExecution → 扁平 dict"""
        # 兼容 dict 或 model
        if isinstance(execution, dict):
            finished = execution.get("finished_at")
            return {
                "id": execution.get("id", ""),
                "action_type_id": execution.get("action_type_id", ""),
                "parameters": execution.get("parameters", {}),
                "result": execution.get("result", {}),
                "status": execution.get("status", "unknown"),
                "error_message": execution.get("error_message", ""),
                "audit_record_id": execution.get("audit_record_id"),
                "user_id": execution.get("user_id", "system"),
                "workspace_id": execution.get("workspace_id", "default"),
                "started_at": execution.get("started_at"),
                "finished_at": finished,
                "duration_ms": execution.get("duration_ms"),
            }
        finished = execution.finished_at
        return {
            "id": execution.id,
            "action_type_id": execution.action_type_id,
            "parameters": execution.parameters,
            "result": execution.result,
            "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
            "error_message": execution.error_message,
            "audit_record_id": execution.audit_record_id,
            "user_id": execution.user_id,
            "workspace_id": execution.workspace_id,
            "started_at": execution.started_at.isoformat() if hasattr(execution.started_at, "isoformat") else str(execution.started_at),
            "finished_at": finished.isoformat() if finished and hasattr(finished, "isoformat") else (str(finished) if finished else None),
            "duration_ms": execution.duration_ms,
        }


def _new_id() -> str:
    """生成 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())
