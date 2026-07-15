"""OODA 生命周期审计钩子

内置 OODA 生命周期钩子，将 OODA 阶段转换记录写入统一审计日志。
遵循任务要求：
- 使用 storage_audit(service="agent_ooda") 优先，回退 log_audit
- 5 阶段 observe/orient/decide/act/evaluate，每阶段 start+end 各一条
- details 含 agent_id、phase、loop_count、workspace_id（如有）
- end 额外含 duration_ms、result_summary_len
- 审计异常 try/except 吞掉，仅 logger.warning
"""

import logging
import time
from typing import Any, Dict, Optional

from odap.biz.core.agent.interfaces.ooda_interface import OODALifecycleHook

logger = logging.getLogger(__name__)


# OODA 规范 5 阶段
_OODA_PHASES = ("observe", "orient", "decide", "act", "evaluate")


def _write_storage_audit(
    action: str,
    resource: str,
    details: Dict[str, Any],
    result_status: str = "success",
    result_message: str = "",
    duration_ms: Optional[int] = None,
) -> None:
    """统一写审计：优先 storage_audit → 回退 log_audit → 再回退 logger

    审计异常绝对不抛到业务层。
    """
    try:
        from odap.infra.security.audit_helper import storage_audit
        _details = dict(details)
        if duration_ms is not None:
            _details.setdefault("duration_ms", duration_ms)
        storage_audit(
            action=action,
            resource=resource,
            details=_details,
            service="agent_ooda",
            result_status=result_status,
            result_message=result_message,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (storage_audit): {e}")

    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource,
            user="system",
            service="agent_ooda",
            details=details,
            result_status=result_status,
            result_message=result_message,
            duration_ms=duration_ms,
        )
        return
    except Exception as e:
        logger.warning(f"audit failed (log_audit fallback): {e}")

    # 终极降级：仅 logger
    logger.info(
        "AUDIT(fallback) | ACTION: %s | RESOURCE: %s | STATUS: %s | DETAILS: %s",
        action, resource, result_status, details,
    )


class AuditOODAHook(OODALifecycleHook):
    """内置 OODA 生命周期钩子，将阶段转换记录写入审计日志。

    5 阶段 observe/orient/decide/act/evaluate，每阶段 start+end 各一条。
    """

    def __init__(self):
        self._phase_start_times: Dict[str, float] = {}
        self._loop_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # observe
    # ------------------------------------------------------------------
    async def on_observe_start(self, context: Dict[str, Any]) -> None:
        await self._on_phase_start("observe", context)

    async def on_observe_end(self, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end("observe", result, context)

    # ------------------------------------------------------------------
    # orient
    # ------------------------------------------------------------------
    async def on_orient_start(self, context: Dict[str, Any]) -> None:
        await self._on_phase_start("orient", context)

    async def on_orient_end(self, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end("orient", result, context)

    # ------------------------------------------------------------------
    # decide
    # ------------------------------------------------------------------
    async def on_decide_start(self, context: Dict[str, Any]) -> None:
        await self._on_phase_start("decide", context)

    async def on_decide_end(self, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end("decide", result, context)

    # ------------------------------------------------------------------
    # act
    # ------------------------------------------------------------------
    async def on_act_start(self, context: Dict[str, Any]) -> None:
        await self._on_phase_start("act", context)

    async def on_act_end(self, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end("act", result, context)

    # ------------------------------------------------------------------
    # evaluate
    # ------------------------------------------------------------------
    async def on_evaluate_start(self, context: Dict[str, Any]) -> None:
        await self._on_phase_start("evaluate", context)

    async def on_evaluate_end(self, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end("evaluate", result, context)

    # ------------------------------------------------------------------
    # 通用钩子（兼容旧接口调用 on_phase_start / on_phase_end）
    # ------------------------------------------------------------------
    async def on_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        await self._on_phase_start(phase, context)

    async def on_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        await self._on_phase_end(phase, result, context)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    async def _on_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """阶段开始审计"""
        self._phase_start_times[phase] = time.monotonic()

        agent_id = context.get("agent_id", context.get("mission_id", "unknown"))
        loop_key = context.get("mission_id", agent_id)
        self._loop_counts[loop_key] = self._loop_counts.get(loop_key, 0) + 1
        loop_count = self._loop_counts[loop_key]
        workspace_id = context.get("workspace_id", context.get("ws_id", "default"))

        details: Dict[str, Any] = {
            "agent_id": agent_id,
            "phase": phase,
            "loop_count": loop_count,
            "workspace_id": workspace_id,
        }
        resource = agent_id

        try:
            _write_storage_audit(
                action=f"ooda_{phase}_start",
                resource=resource,
                details=details,
                result_status="success",
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

        logger.info(
            "AuditOODAHook: OODA %s 阶段 start (agent=%s, loop=%s, ws=%s)",
            phase, agent_id, loop_count, workspace_id,
        )

    async def _on_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """阶段结束审计（含耗时 + 结果摘要长度）"""
        start_time = self._phase_start_times.pop(phase, None)
        duration_ms = int((time.monotonic() - start_time) * 1000) if start_time else None

        agent_id = context.get("agent_id", context.get("mission_id", "unknown"))
        loop_key = context.get("mission_id", agent_id)
        loop_count = self._loop_counts.get(loop_key, 1)
        workspace_id = context.get("workspace_id", context.get("ws_id", "default"))

        try:
            result_summary_len = len(str(result)[:200]) if result is not None else 0
        except Exception:
            result_summary_len = 0

        result_status = "success"
        result_message = ""
        if isinstance(result, Exception):
            result_status = "failure"
            result_message = str(result)[:500]
        elif isinstance(result, dict) and result.get("status") in ("error", "failed", "failure"):
            result_status = "failure"
            result_message = str(result.get("message", ""))[:500]

        details: Dict[str, Any] = {
            "agent_id": agent_id,
            "phase": phase,
            "loop_count": loop_count,
            "workspace_id": workspace_id,
            "duration_ms": duration_ms or 0,
            "result_summary_len": result_summary_len,
        }
        resource = agent_id

        try:
            _write_storage_audit(
                action=f"ooda_{phase}_end",
                resource=resource,
                details=details,
                result_status=result_status,
                result_message=result_message,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.warning(f"audit failed: {e}")

        logger.info(
            "AuditOODAHook: OODA %s 阶段 end (agent=%s, loop=%s, duration=%sms, summary_len=%s)",
            phase, agent_id, loop_count, duration_ms, result_summary_len,
        )
