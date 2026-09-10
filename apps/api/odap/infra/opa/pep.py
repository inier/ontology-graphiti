#!/usr/bin/env python3
"""
策略执行点 (Policy Enforcement Point)

白皮书 §3 运行时执行流编排：
  意图 → 白名单校验 → OPA ABAC 评估 → 决策执行 → 审计

职责：
1. 工具白名单校验（不在白名单直接 BLOCKED，不进入 OPA）
2. 调用 OPAManager 进行 ABAC 评估
3. 串联 PreToolUse / PostToolUse Hook
4. 统一写审计（含 agent_id, trace_id, input_context, output_artifact）
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class EnforcementRequest:
    """PEP 执行请求"""
    agent_id: str
    tool_name: str
    action: str
    resource: Dict[str, Any]
    subject: Dict[str, Any]          # user_id, roles, clearance_level, workspace_id
    environment: Dict[str, Any]      # time, ip, session_duration_seconds
    input_context: Dict[str, Any]    # 工具调用输入参数
    trace_id: str = ""
    session_id: str = ""


@dataclass
class EnforcementResult:
    """PEP 执行结果"""
    allowed: bool
    reason: str
    stage: str                       # "whitelist" | "opa" | "executed"
    opa_decision: Optional[Dict] = None
    output_artifact: Optional[Dict] = None
    blocked_at: Optional[str] = None # "whitelist" | "opa" | None


class PolicyEnforcementPoint:
    """统一策略执行点 — 白皮书 §3 完整流程编排"""

    def __init__(self, opa_manager, hook_registry=None, allowed_tools: List[str] = None):
        self.opa = opa_manager
        self.hooks = hook_registry
        self.allowed_tools = set(allowed_tools or [])

    def evaluate(self, req: EnforcementRequest) -> EnforcementResult:
        """执行白皮书 §3 完整流程"""
        # Stage 1: 白名单校验 (PEP)
        if req.tool_name not in self.allowed_tools:
            result = EnforcementResult(
                allowed=False,
                reason=f"Tool '{req.tool_name}' not in allow-list",
                stage="whitelist",
                blocked_at="whitelist",
            )
            self._audit(req, result)
            return result

        # Stage 2: PreToolUse Hook
        self._fire_hook("pre_tool_use", req)

        # Stage 3: OPA ABAC 评估
        try:
            opa_result = self.opa.check_permission_abac(
                user=req.subject,
                action=req.action,
                resource=req.resource,
                environment=req.environment,
            )
        except Exception as e:
            opa_result = {"allow": False, "reason": f"OPA evaluation error: {e}"}

        if not opa_result.get("allow", False):
            result = EnforcementResult(
                allowed=False,
                reason=opa_result.get("reason", "OPA denied"),
                stage="opa",
                opa_decision=opa_result,
                blocked_at="opa",
            )
            self._audit(req, result)
            self._push_deny_to_agent(req, result)  # P2-06: DENY 回传 Agent
            self._fire_hook("post_tool_use", req, result)
            return result

        # Stage 4: 决策执行（由调用方执行工具，PEP 仅返回 ALLOW）
        result = EnforcementResult(
            allowed=True,
            reason="Permission granted",
            stage="executed",
            opa_decision=opa_result,
        )
        self._audit(req, result)
        return result

    def record_execution(self, req: EnforcementRequest, output_artifact: Dict):
        """工具执行完成后记录 output_artifact（PostToolUse）

        P3-03: 白皮书 §2.3 — 审计日志含 input_context + output_artifact
        """
        self._fire_hook("post_tool_use", req, output_artifact=output_artifact)
        # 写审计 — 补充 output_artifact（脱敏）
        try:
            from odap.infra.security.unified_audit import log_audit
            from odap.infra.security.audit_sanitizer import sanitize_audit_data
            log_audit(
                action=f"tool_executed:{req.tool_name}",
                resource=req.resource.get("id", req.tool_name),
                user=req.agent_id,
                service="pep",
                details={
                    "trace_id": req.trace_id,
                    "input_context": sanitize_audit_data(req.input_context),
                    "output_artifact": sanitize_audit_data(output_artifact),
                    "opa_decision": "allow",
                },
            )
        except Exception as e:
            logger.warning(f"PostToolUse 审计写入失败: {e}")

    def _fire_hook(self, event: str, req: EnforcementRequest,
                   result: EnforcementResult = None, output_artifact: Dict = None):
        """触发 Hook 事件"""
        if not self.hooks:
            return
        try:
            from odap.infra.events import HookRegistry as _HR, HookPhase, HookContext
            registry = _HR.get_instance()
            ctx = HookContext(event_name=event)
            payload = {
                "agent_id": req.agent_id,
                "tool_name": req.tool_name,
                "action": req.action,
                "trace_id": req.trace_id,
                "result": result.__dict__ if result else None,
                "output_artifact": output_artifact,
            }
            ctx.set_data("payload", payload)
            for hook in registry.get_hooks(event, HookPhase.POST):
                try:
                    hook.handler(ctx, payload)
                except Exception as e:
                    logger.warning(f"Hook {event} handler 执行失败: {e}")
        except Exception as e:
            logger.warning(f"Hook {event} 触发失败: {e}")

    def _audit(self, req: EnforcementRequest, result: EnforcementResult):
        """统一审计写入（含 agent_id, trace_id, input_context）"""
        try:
            from odap.infra.security.unified_audit import audit_opa_decision
            audit_opa_decision(
                subject=req.agent_id,
                action=f"{req.tool_name}:{req.action}",
                resource=req.resource.get("id", req.resource.get("type", "unknown")),
                result="allow" if result.allowed else "deny",
                reason=result.reason,
                policy_version=self.opa.get_bundle_version(),
            )
        except Exception as e:
            logger.warning(f"PEP 审计写入失败: {e}")

    def _push_deny_to_agent(self, req: EnforcementRequest, result: EnforcementResult):
        """P2-06: 白皮书 §3 — DENY 原因反馈 Agent 上下文"""
        try:
            import asyncio
            from odap.infra.events.event_bus import get_event_bus
            bus = get_event_bus()
            data = {
                "agent_id": req.agent_id,
                "trace_id": req.trace_id,
                "tool_name": req.tool_name,
                "reason": result.reason,
                "opa_decision": result.opa_decision,
            }
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(bus.emit(f"agent:{req.agent_id}:denied", data))
                else:
                    loop.run_until_complete(bus.emit(f"agent:{req.agent_id}:denied", data))
            except RuntimeError:
                asyncio.run(bus.emit(f"agent:{req.agent_id}:denied", data))
        except Exception as e:
            logger.warning(f"DENY 回传 Agent 失败: {e}")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_pep_instance: Optional[PolicyEnforcementPoint] = None


def get_pep_instance() -> PolicyEnforcementPoint:
    """获取 PEP 全局单例，从环境变量读取白名单配置"""
    global _pep_instance
    if _pep_instance is None:
        from odap.infra.opa.opa_service import OPAManager
        allowed_tools_str = os.environ.get("OPA_ALLOWED_TOOLS", "")
        allowed_tools = [t.strip() for t in allowed_tools_str.split(",") if t.strip()]
        _pep_instance = PolicyEnforcementPoint(
            opa_manager=OPAManager(),
            allowed_tools=allowed_tools,
        )
    return _pep_instance


def reset_pep_instance():
    """重置单例（测试用）"""
    global _pep_instance
    _pep_instance = None


__all__ = [
    "EnforcementRequest",
    "EnforcementResult",
    "PolicyEnforcementPoint",
    "get_pep_instance",
    "reset_pep_instance",
]
