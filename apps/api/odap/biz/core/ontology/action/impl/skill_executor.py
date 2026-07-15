"""SkillBackedExecutor (T382)

Action Type 默认执行器：Action = 业务接口 → 通过 linked_skill_id 委托给 Skill。

执行流程：
1. 校验 linked_skill_id 非空
2. 从 skill_registry 取出 Skill
3. 调用 Skill（run / execute）
4. 异常 → status=FAILED, error_message 描述
5. 成功 → status=SUCCESS, result 包含 SkillOutput.data
6. 调用 storage_audit(service="agent_skill") 写审计（start/success/failed 三维度）

审计要求：
- execute_skill 入口记 skill_execute_start（agent_id, skill_name, args_count）
- 成功记 skill_execute_success（agent_id, skill_name, latency_ms, result_len）
- 失败记 skill_execute_failed（re-raise 原异常）
- 如有 batch_execute / run_skill_sequence，每条 step 各一条 start/end
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces import ActionExecutor
from ..models import ActionExecution, ActionExecutionStatus, ActionType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 审计辅助（统一接口 + 容错，绝不打断业务）
# ---------------------------------------------------------------------------

def _skill_audit(
    action: str,
    *,
    skill_id: str,
    agent_id: str = "system",
    skill_name: str = "",
    args_count: Optional[int] = None,
    latency_ms: Optional[int] = None,
    result_len: Optional[int] = None,
    success_flag: Optional[bool] = None,
    result_status: str = "success",
    result_message: str = "",
) -> None:
    """Skill 执行审计：优先 storage_audit → 回退 log_audit → 回退 logger.warning

    Args:
        action: "skill_execute_start" | "skill_execute_success" | "skill_execute_failed"
                "batch_step_start" | "batch_step_end"
        skill_id: Skill 的唯一标识（resource）
        agent_id: 触发 Agent ID（无则 system）
        skill_name: Skill 可读名
        args_count: 参数个数（start 时记录）
        latency_ms: 耗时毫秒（success/failed 时记录）
        result_len: 结果摘要长度（success 时记录）
        success_flag: 成功标记布尔值
        result_status: "success" | "failure"
        result_message: 失败时错误信息（截断 500 字）
    """
    details: Dict[str, Any] = {
        "agent_id": agent_id or "system",
        "skill_name": skill_name or skill_id,
    }
    if args_count is not None:
        details["args_count"] = args_count
    if latency_ms is not None:
        details["latency_ms"] = latency_ms
    if result_len is not None:
        details["result_len"] = result_len
    if success_flag is not None:
        details["success_flag"] = bool(success_flag)

    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            resource=skill_id,
            details=details,
            service="agent_skill",
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
            resource=skill_id,
            user="system",
            service="agent_skill",
            details=details,
            result_status=result_status,
            result_message=result_message,
            duration_ms=latency_ms,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (log_audit fallback): {e}")


class SkillBackedExecutor(ActionExecutor):
    """基于 Skill 系统的 Action 执行器"""

    def __init__(self, skill_registry: Any = None, audit_sink: Any = None,
                 executor_id: str = "skill-backed"):
        self._skill_registry = skill_registry
        self._audit_sink = audit_sink
        self._executor_id = executor_id

    # ------------------------------------------------------------------
    # 主入口：单 Skill 执行
    # ------------------------------------------------------------------

    def execute(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """执行 ActionType 并返回 ActionExecution

        审计：
        - 入口：skill_execute_start
        - try 成功：skill_execute_success
        - except 失败：skill_execute_failed + re-raise 原异常
        """
        execution = self._init_execution(action_type, parameters, user_context)
        if not action_type.linked_skill_id:
            return self._fail(execution, "linked_skill_id is required")

        skill_id = action_type.linked_skill_id
        agent_id = user_context.get("agent_id", user_context.get("user_id", "system"))
        skill_name = action_type.name or skill_id
        args_count = len(parameters or {})

        # 【审计】入口 start
        try:
            _skill_audit(
                "skill_execute_start",
                skill_id=skill_id,
                agent_id=agent_id,
                skill_name=skill_name,
                args_count=args_count,
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

        registry = self._resolve_registry()
        if registry is None:
            # 审计失败（registry 不可用）但不抛异常，返回失败 execution
            try:
                _skill_audit(
                    "skill_execute_failed",
                    skill_id=skill_id,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    result_status="failure",
                    result_message="Skill registry unavailable",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._fail(execution, "Skill registry unavailable")

        skill = registry.get(skill_id)
        if skill is None:
            try:
                _skill_audit(
                    "skill_execute_failed",
                    skill_id=skill_id,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    result_status="failure",
                    result_message=f"Skill not found: {skill_id}",
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._fail(
                execution,
                f"Skill not found: {skill_id}",
            )

        return self._invoke_skill(
            execution, skill, parameters, user_context,
            skill_id=skill_id, agent_id=agent_id, skill_name=skill_name,
        )

    # ------------------------------------------------------------------
    # 批量 / 序列执行（如存在则每 step 一条 start/end）
    # ------------------------------------------------------------------

    def batch_execute(
        self,
        action_types: List[ActionType],
        parameters_list: List[Dict[str, Any]],
        user_context: Dict[str, Any],
    ) -> List[ActionExecution]:
        """批量执行多个 Skill，每个 step 单独审计 start/end"""
        results: List[ActionExecution] = []
        agent_id = user_context.get("agent_id", user_context.get("user_id", "system"))
        for idx, (at, params) in enumerate(zip(action_types, parameters_list)):
            skill_id = at.linked_skill_id or f"step_{idx}"
            skill_name = at.name or skill_id
            args_count = len(params or {})
            # batch step start 审计
            try:
                _skill_audit(
                    "batch_step_start",
                    skill_id=skill_id,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    args_count=args_count,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            start = time.perf_counter()
            try:
                result = self.execute(at, params, user_context)
                latency_ms = int((time.perf_counter() - start) * 1000)
                # batch step end 成功
                try:
                    _skill_audit(
                        "batch_step_end",
                        skill_id=skill_id,
                        agent_id=agent_id,
                        skill_name=skill_name,
                        latency_ms=latency_ms,
                        success_flag=(result.status == ActionExecutionStatus.SUCCESS),
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
            except Exception as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                # batch step end 失败
                try:
                    _skill_audit(
                        "batch_step_end",
                        skill_id=skill_id,
                        agent_id=agent_id,
                        skill_name=skill_name,
                        latency_ms=latency_ms,
                        success_flag=False,
                        result_status="failure",
                        result_message=str(e)[:500],
                    )
                except Exception as e_a:
                    logger.warning(f"audit failed: {e_a}")
                raise
            results.append(result)
        return results

    def run_skill_sequence(
        self,
        skill_ids: List[str],
        parameters_list: List[Dict[str, Any]],
        user_context: Dict[str, Any],
    ) -> List[Any]:
        """按序列执行 Skill ID 列表，每 step 单独 start/end 审计"""
        results: List[Any] = []
        agent_id = user_context.get("agent_id", user_context.get("user_id", "system"))
        registry = self._resolve_registry()
        for idx, (sid, params) in enumerate(zip(skill_ids, parameters_list)):
            skill_name = sid
            args_count = len(params or {})
            try:
                _skill_audit(
                    "skill_sequence_step_start",
                    skill_id=sid,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    args_count=args_count,
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            start = time.perf_counter()
            try:
                registry_ref = registry or self._resolve_registry()
                skill_obj = registry_ref.get(sid) if registry_ref else None
                if skill_obj is None:
                    raise RuntimeError(f"Skill not found in sequence: {sid}")
                output = self._call_skill(skill_obj, params, user_context)
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    result_len = len(str(output)[:200]) if output is not None else 0
                except Exception:
                    result_len = 0
                try:
                    _skill_audit(
                        "skill_sequence_step_end",
                        skill_id=sid,
                        agent_id=agent_id,
                        skill_name=skill_name,
                        latency_ms=latency_ms,
                        result_len=result_len,
                        success_flag=True,
                    )
                except Exception as e:
                    logger.warning(f"audit failed: {e}")
                results.append(output)
            except Exception as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                try:
                    _skill_audit(
                        "skill_sequence_step_end",
                        skill_id=sid,
                        agent_id=agent_id,
                        skill_name=skill_name,
                        latency_ms=latency_ms,
                        success_flag=False,
                        result_status="failure",
                        result_message=str(e)[:500],
                    )
                except Exception as e_a:
                    logger.warning(f"audit failed: {e_a}")
                raise
        return results

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

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
        *,
        skill_id: str,
        agent_id: str,
        skill_name: str,
    ) -> ActionExecution:
        """调用 Skill；统一处理异常 / 结果 + 成功/失败审计

        异常路径：先记 skill_execute_failed 审计 → re-raise 原异常
        """
        start = time.perf_counter()
        try:
            output = self._call_skill(skill, parameters, user_context)
        except TimeoutError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            # 【审计】失败 - 记 skill_execute_failed
            try:
                _skill_audit(
                    "skill_execute_failed",
                    skill_id=skill_id,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    latency_ms=latency_ms,
                    success_flag=False,
                    result_status="failure",
                    result_message=f"Skill execution timeout: {exc}"[:500],
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._fail(execution, f"Skill execution timeout: {exc}")
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            # 【审计】失败 - 记 skill_execute_failed
            try:
                _skill_audit(
                    "skill_execute_failed",
                    skill_id=skill_id,
                    agent_id=agent_id,
                    skill_name=skill_name,
                    latency_ms=latency_ms,
                    success_flag=False,
                    result_status="failure",
                    result_message=f"Skill execution error: {exc}"[:500],
                )
            except Exception as e:
                logger.warning(f"audit failed: {e}")
            return self._fail(execution, f"Skill execution error: {exc}")

        latency_ms = int((time.perf_counter() - start) * 1000)
        execution.duration_ms = latency_ms
        execution.finished_at = datetime.now()

        # 【审计】成功 - 记 skill_execute_success
        try:
            try:
                result_len = len(str(output)[:200]) if output is not None else 0
            except Exception:
                result_len = 0
            _skill_audit(
                "skill_execute_success",
                skill_id=skill_id,
                agent_id=agent_id,
                skill_name=skill_name,
                latency_ms=latency_ms,
                result_len=result_len,
                success_flag=True,
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

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
        """调用 unified_audit.log_audit 写审计；失败不抛（兼容原有路径）"""
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
