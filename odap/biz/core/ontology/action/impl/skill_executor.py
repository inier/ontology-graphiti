"""SkillBackedExecutor (T382)

Action Type 默认执行器：Action = 业务接口 → 通过 linked_skill_id 委托给 Skill。

执行流程：
1. 校验 linked_skill_id 非空
2. 从 skill_registry 取出 Skill
3. 调用 Skill（run / execute）
4. 异常 → status=FAILED, error_message 描述
5. 成功 → status=SUCCESS, result 包含 SkillOutput.data
6. 调用 unified_audit.log_audit 写审计
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from ..interfaces import ActionExecutor
from ..models import ActionExecution, ActionExecutionStatus, ActionType

logger = logging.getLogger(__name__)


class SkillBackedExecutor(ActionExecutor):
    """基于 Skill 系统的 Action 执行器"""

    def __init__(self, skill_registry: Any = None, audit_sink: Any = None,
                 executor_id: str = "skill-backed"):
        self._skill_registry = skill_registry
        self._audit_sink = audit_sink
        self._executor_id = executor_id

    def _resolve_registry(self) -> Any:
        """懒加载默认 SkillRegistry"""
        if self._skill_registry is not None:
            return self._skill_registry
        try:
            from odap.tools.base import get_registry
            return get_registry()
        except Exception as exc:  # 缺依赖也不阻塞测试
            logger.warning("SkillRegistry not available: %s", exc)
            return None

    def execute(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """执行 ActionType 并返回 ActionExecution"""
        execution = self._init_execution(action_type, parameters, user_context)
        if not action_type.linked_skill_id:
            return self._fail(execution, "linked_skill_id is required")

        registry = self._resolve_registry()
        if registry is None:
            return self._fail(execution, "Skill registry unavailable")

        skill = registry.get(action_type.linked_skill_id)
        if skill is None:
            return self._fail(
                execution,
                f"Skill not found: {action_type.linked_skill_id}",
            )

        return self._invoke_skill(execution, skill, parameters, user_context)

    def _init_execution(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """构造初始 execution（PENDING → RUNNING）"""
        return ActionExecution(
            action_type_id=action_type.id,
            parameters=parameters,
            status=ActionExecutionStatus.RUNNING,
            user_id=user_context.get("user_id", "system"),
            workspace_id=user_context.get("ws_id", "default"),
        )

    def _invoke_skill(
        self,
        execution: ActionExecution,
        skill: Any,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """调用 Skill；统一处理异常 / 结果"""
        start = time.perf_counter()
        try:
            output = self._call_skill(skill, parameters, user_context)
        except TimeoutError as exc:
            return self._fail(execution, f"Skill execution timeout: {exc}")
        except Exception as exc:
            return self._fail(execution, f"Skill execution error: {exc}")
        execution.duration_ms = int((time.perf_counter() - start) * 1000)
        execution.finished_at = datetime.now()
        return self._apply_output(execution, output)

    def _call_skill(self, skill: Any, parameters: Dict[str, Any],
                    user_context: Dict[str, Any]) -> Any:
        """统一调用 Skill 的入口：BaseSkill.run() 或 handler()"""
        if hasattr(skill, "run"):
            return skill.run(parameters or {})
        if callable(skill):
            return skill(**(parameters or {}))
        if hasattr(skill, "execute"):
            from odap.tools.base import SkillInput
            return skill.execute(SkillInput(**(parameters or {})))
        raise RuntimeError("Skill object is not callable")

    def _apply_output(self, execution: ActionExecution, output: Any) -> ActionExecution:
        """把 SkillOutput / dict / 任意值映射到 execution"""
        if output is None:
            execution.status = ActionExecutionStatus.SUCCESS
            execution.result = {}
            return self._finalize(execution)

        if hasattr(output, "success") and hasattr(output, "data"):
            execution.result = dict(output.data or {})
            if output.error:
                execution.error_message = str(output.error)
            execution.status = (
                ActionExecutionStatus.SUCCESS
                if output.success
                else ActionExecutionStatus.FAILED
            )
            return self._finalize(execution)

        if isinstance(output, dict):
            if output.get("status") == "denied":
                execution.status = ActionExecutionStatus.DENIED
                execution.error_message = output.get("message", "denied")
                execution.result = output
                return self._finalize(execution)
            execution.result = output
            execution.status = ActionExecutionStatus.SUCCESS
            return self._finalize(execution)

        execution.result = {"result": output}
        execution.status = ActionExecutionStatus.SUCCESS
        return self._finalize(execution)

    def _fail(self, execution: ActionExecution, message: str) -> ActionExecution:
        """统一失败处理：填 error_message / FAILED / finished_at / duration_ms"""
        execution.status = ActionExecutionStatus.FAILED
        execution.error_message = message
        execution.finished_at = datetime.now()
        if execution.duration_ms is None and execution.started_at:
            try:
                delta = (execution.finished_at - execution.started_at).total_seconds()
                execution.duration_ms = int(delta * 1000)
            except Exception:  # 时区差等异常吞掉
                execution.duration_ms = None
        return self._audit(execution)

    def _finalize(self, execution: ActionExecution) -> ActionExecution:
        """成功执行也走审计（仅写入记录）"""
        return self._audit(execution)

    def _audit(self, execution: ActionExecution) -> ActionExecution:
        """调用 unified_audit.log_audit 写审计；失败不抛"""
        sink = self._audit_sink
        if sink is None:
            try:
                from odap.infra.security.unified_audit import log_audit
                sink = log_audit
            except Exception as exc:
                logger.warning("audit sink unavailable: %s", exc)
                return execution
        try:
            details = {
                "action_type_id": execution.action_type_id,
                "status": execution.status.value,
                "duration_ms": execution.duration_ms,
            }
            record_id = sink(
                action=f"action.execute.{execution.status.value}",
                resource=execution.action_type_id,
                user=execution.user_id,
                service="action",
                details=details,
            )
            if isinstance(record_id, str) and record_id:
                execution.audit_record_id = record_id
        except Exception as exc:  # 审计失败不影响主流程
            logger.warning("audit log failed: %s", exc)
        return execution
