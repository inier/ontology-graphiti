"""OODA 生命周期审计钩子

内置 OODA 生命周期钩子，将 OODA 阶段转换记录写入统一审计日志。
遵循 AGENTS.md 规则 10：所有变更通过 unified_audit.py 统一写入。
"""

import logging
import time
from typing import Any, Dict

from odap.biz.core.agent.interfaces.ooda_interface import OODALifecycleHook

logger = logging.getLogger(__name__)


class AuditOODAHook(OODALifecycleHook):
    """内置 OODA 生命周期钩子，将阶段转换记录写入审计日志。

    当 unified_audit.log_audit() 可用时写入审计日志，
    否则降级为标准 logger.info() 输出。
    """

    def __init__(self):
        self._phase_start_times: Dict[str, float] = {}
        self._audit_available: bool = True
        # 首次检测 unified_audit 是否可用
        try:
            from odap.infra.security.unified_audit import log_audit  # noqa: F401
            self._audit_available = True
        except ImportError:
            self._audit_available = False

    async def on_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """阶段开始时记录审计日志"""
        self._phase_start_times[phase] = time.monotonic()

        mission_id = context.get("mission_id", context.get("agent_id", "unknown"))
        description = f"OODA {phase} 阶段开始 (mission={mission_id})"

        self._write_audit(
            action=f"ooda_{phase}_start",
            resource=mission_id,
            service="ooda_lifecycle",
            details={"phase": phase, "mission_id": mission_id},
        )

        logger.info("AuditOODAHook: %s", description)

    async def on_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """阶段结束时记录审计日志（含耗时和结果摘要）"""
        start_time = self._phase_start_times.pop(phase, None)
        duration_ms = int((time.monotonic() - start_time) * 1000) if start_time else None

        mission_id = context.get("mission_id", context.get("agent_id", "unknown"))
        result_summary = str(result)[:200] if result else ""

        self._write_audit(
            action=f"ooda_{phase}_end",
            resource=mission_id,
            service="ooda_lifecycle",
            details={
                "phase": phase,
                "mission_id": mission_id,
                "duration_ms": duration_ms,
                "result_summary": result_summary,
            },
        )

        logger.info(
            "AuditOODAHook: OODA %s 阶段结束 (mission=%s, duration=%sms)",
            phase, mission_id, duration_ms,
        )

    def _write_audit(self, action: str, resource: str, service: str,
                      details: Dict[str, Any]) -> None:
        """写入审计日志（优雅降级）"""
        if not self._audit_available:
            logger.info(
                "AUDIT(unified_unavailable) | ACTION: %s | RESOURCE: %s | SERVICE: %s | DETAILS: %s",
                action, resource, service, details,
            )
            return

        try:
            from odap.infra.security.unified_audit import log_audit
            log_audit(
                action=action,
                resource=resource,
                user="system",
                service=service,
                details=details,
            )
        except Exception as e:
            logger.warning("AuditOODAHook: log_audit failed, falling back to logger: %s", e)
            self._audit_available = False
            logger.info(
                "AUDIT(fallback) | ACTION: %s | RESOURCE: %s | SERVICE: %s | DETAILS: %s",
                action, resource, service, details,
            )
