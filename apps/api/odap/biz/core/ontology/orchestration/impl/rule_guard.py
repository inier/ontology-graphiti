"""规则校验：OPA 策略执行 + fail-closed（AC-28）。

语义（SPEC AC-28 逐字）：
    If OPA 不可用 → RuleGuard **必须**拒绝高风险动作（`503 GUARD_FAIL_CLOSED`），
    只读查询放行并标 `degraded=true`。

实现：
- 复用 `odap.infra.opa.opa_service.OPAManager.check_permission_abac`（真实 OPA HTTP 调用）；
  OPA 不可达时该方法抛异常，本类据此判定「不可用」。
- 风险评估是**确定性词典**（不含 LLM）：命中写/删类动词即高风险。
- OPA 可用但拒绝时不抛 503，而是返回 `allowed=false` + `violations=[reason]`
  （这是策略拒绝，不是系统故障，管线会给出 blocked 响应）。

证据：`opa_decision` ref 指向 `policies/ontology_assistant.rego#allow`
（AC-37 要求可解析 —— 校验器会确认该 rego 文件与规则确实存在）。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.core.ontology.orchestration.contracts import (
    Evidence,
    GuardResult,
    MappedQuery,
    StepProv,
)

logger = logging.getLogger(__name__)

POLICY_REF = "policies/ontology_assistant.rego#allow"

#: 高风险动作词典（写入/删除/执行类；确定性，可审计）
HIGH_RISK_PATTERNS: Sequence[str] = (
    "删除", "删掉", "清空", "移除", "写入", "更新", "修改", "执行", "落库",
    "覆盖", "drop", "delete", "truncate", "update", "insert", "remove", "rm ",
)

#: 只读意图（OPA 不可用时允许放行并标 degraded）
READ_ONLY_INTENTS = frozenset({
    "concept_lookup", "relation_lookup", "metric_query", "property_lookup",
    "process_lookup", "rule_lookup", "unknown",
})


def classify_risk(mapped: MappedQuery) -> str:
    """判定风险等级：`high` / `low`。"""
    if mapped.intent.intent_type == "action_request":
        return "high"
    text = " ".join(
        [str(mapped.intent.slots.get("query") or "")]
        + [str(t) for t in (mapped.intent.slots.get("terms") or [])]
    ).lower()
    if any(pattern in text for pattern in HIGH_RISK_PATTERNS):
        return "high"
    return "low" if mapped.intent.intent_type in READ_ONLY_INTENTS else "high"


class OPARuleGuard:
    """OPA 策略守卫（插槽实现）。"""

    name = "RuleGuard"
    version = "v2.0"

    def __init__(
        self,
        opa_manager_factory: Optional[Callable[[], Any]] = None,
        policy_ref: str = POLICY_REF,
    ) -> None:
        self._factory = opa_manager_factory or _default_opa_manager
        self.policy_ref = policy_ref

    async def check(self, mapped: MappedQuery, user_ctx: Dict[str, Any],
                    workspace_id: str) -> GuardResult:
        prov = StepProv(component=self.name, version=self.version)
        risk = classify_risk(mapped)
        action = "ontology_qa.write" if risk == "high" else "ontology_qa.read"
        subject = {
            "id": str(user_ctx.get("sub") or user_ctx.get("user_id") or "anonymous"),
            "roles": list(user_ctx.get("roles") or ([user_ctx["role"]]
                                                    if user_ctx.get("role") else [])),
            "attributes": {"workspace_id": workspace_id},
        }
        resource = {
            "type": "OntologyQuery",
            "attributes": {"intent_type": mapped.intent.intent_type, "risk_level": risk,
                           "workspace_id": workspace_id},
        }

        try:
            decision = await asyncio.to_thread(
                self._evaluate, subject, action, resource
            )
        except Exception as exc:  # noqa: BLE001 - OPA 不可用 → 按 AC-28 处理
            logger.error(
                "OPA 不可用：error_code=%s action=%s risk=%s error_type=%s error=%s",
                E.GUARD_FAIL_CLOSED, action, risk, type(exc).__name__, exc,
            )
            if risk == "high":
                raise ApiError(
                    E.GUARD_FAIL_CLOSED,
                    f"OPA 策略引擎不可用，按 fail-closed 拒绝高风险动作（action={action}）："
                    f"{type(exc).__name__}: {exc}",
                    status_code=503,
                    detail={"action": action, "risk_level": risk,
                            "workspace_id": workspace_id},
                ) from exc
            prov.evidence.append(
                Evidence(kind="decision", ref="decision:guard_degraded_opa_unavailable")
            )
            return GuardResult(
                allowed=True, risk_level=risk, degraded=True, decision_ref=None, prov=prov,
            )

        allow = bool(decision.get("allow"))
        prov.evidence.append(
            Evidence(kind="opa_decision", ref=self.policy_ref, decision=allow)
        )
        violations = [] if allow else [str(decision.get("reason") or "OPA denied")]
        return GuardResult(
            allowed=allow,
            risk_level=risk,
            violations=violations,
            degraded=False,
            decision_ref=self.policy_ref,
            prov=prov,
        )

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _evaluate(self, subject: Dict[str, Any], action: str,
                  resource: Dict[str, Any]) -> Dict[str, Any]:
        manager = self._factory()
        return manager.check_permission_abac(
            user=subject, action=action, resource=resource, environment={}
        )


def _default_opa_manager() -> Any:
    from odap.infra.opa.opa_service import OPAManager

    return OPAManager()


def policy_ref_exists(policy_ref: str = POLICY_REF) -> bool:
    """校验 `policy#rule` 指向的 rego 文件与规则名真实存在（AC-37 证据解析）。"""
    path_part, _, rule = policy_ref.partition("#")
    if not path_part:
        return False
    # odap/biz/core/ontology/orchestration/impl/rule_guard.py → parents[5] == odap/
    base = Path(__file__).resolve().parents[5] / "infra" / "opa"
    candidate = base / path_part
    if not candidate.is_file():
        return False
    if not rule:
        return True
    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"{rule} " in content or f"{rule}," in content or f"{rule}:" in content


__all__ = [
    "OPARuleGuard",
    "classify_risk",
    "policy_ref_exists",
    "HIGH_RISK_PATTERNS",
    "POLICY_REF",
]
