"""六步约束管线编排器（F6 / F8）。

管线：IntentRouter → OntologyAligner → RuleGuard → RetrievalExecutor →
      AnswerComposer → OutputContractGate

编排纪律：
- 只依赖六个 Protocol（`contracts.py`），实现可替换（§8.2 接口即插槽）。
- **每一步都产出 provenance**，包括 clarify / blocked 分支（用 `decision:*` 证据显式声明
  「该步未执行及其原因」），保证任何响应都覆盖六步（AC-36）。
- 失败语义：业务拒绝抛 `ApiError`（fail-closed）；降级在信封里显式标注，不隐藏。
- 本轮不做：L3 LLM 消歧、检索重排、Action/HITL 执行（见各 TODO 与未完成清单）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from odap.common.ids import new_trace_id
from odap.biz.core.ontology.orchestration.actions.derive import derive_actions
from odap.biz.core.ontology.orchestration.actions.service import ActionService
from odap.biz.core.ontology.orchestration.contracts import (
    AnswerEnvelope,
    Evidence,
    QaStatus,
    StepProv,
)
from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver
from odap.biz.core.ontology.orchestration.impl.answer_composer import (
    EvidenceOnlyAnswerComposer,
)
from odap.biz.core.ontology.orchestration.impl.intent_router import L1IntentRouter
from odap.biz.core.ontology.orchestration.impl.ontology_aligner import TBoxOntologyAligner
from odap.biz.core.ontology.orchestration.impl.output_contract_gate import (
    StrictOutputContractGate,
)
from odap.biz.core.ontology.orchestration.impl.retrieval_executor import (
    MultiEngineRetrievalExecutor,
)
from odap.biz.core.ontology.orchestration.impl.rule_guard import OPARuleGuard
from odap.biz.core.ontology.orchestration.provenance import (
    Provenance,
    ProvenanceBuilder,
    validate_provenance,
)
from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository
from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.9


def _decision(step_component: str, ref: str) -> StepProv:
    return StepProv(component=step_component, version="v2.0",
                    evidence=[Evidence(kind="decision", ref=ref)])


class QaPipeline:
    """本体约束问答管线。"""

    def __init__(
        self,
        intent_router=None,
        aligner=None,
        guard=None,
        retriever=None,
        composer=None,
        gate=None,
        trace_repo: Optional[QaTraceRepository] = None,
        catalog: Optional[TBoxCatalog] = None,
        resolver=None,
        action_service: Optional[ActionService] = None,
    ) -> None:
        self.catalog = catalog or TBoxCatalog()
        self.intent_router = intent_router or L1IntentRouter()
        self.aligner = aligner or TBoxOntologyAligner(self.catalog)
        self.guard = guard or OPARuleGuard()
        self.retriever = retriever or MultiEngineRetrievalExecutor()
        self.composer = composer or EvidenceOnlyAnswerComposer()
        self.gate = gate or StrictOutputContractGate()
        self.trace_repo = trace_repo or QaTraceRepository()
        self.resolver = resolver or DefaultEvidenceResolver(catalog=self.catalog)
        self.action_service = action_service or ActionService(trace_repo=self.trace_repo)

    async def run(
        self,
        *,
        query: str,
        user_ctx: Dict[str, Any],
        workspace_id: str = "",
        mode: str = "auto",
        allow_actions: bool = False,
    ) -> Tuple[AnswerEnvelope, Provenance]:
        trace_id = new_trace_id()
        builder = ProvenanceBuilder(trace_id)
        user_id = str(user_ctx.get("sub") or user_ctx.get("user_id") or "")

        # ── [1] intent ────────────────────────────────────────────────────
        intent = await self.intent_router.route(query, user_ctx, workspace_id)
        builder.add("intent", intent.prov)

        if intent.intent_type == "unknown" or intent.confidence < CONFIDENCE_THRESHOLD:
            envelope, provenance = self._clarify(trace_id, builder, intent, workspace_id,
                                                 query, user_id)
            return await self._finish(envelope, provenance, query, workspace_id, user_id,
                                      intent=intent.model_dump(mode="json"),
                                      allow_actions=allow_actions)

        # ── [2] map ───────────────────────────────────────────────────────
        mapped = await self.aligner.align(intent, workspace_id)
        builder.add("map", mapped.prov)

        # ── [3] guard ─────────────────────────────────────────────────────
        guard = await self.guard.check(mapped, user_ctx, workspace_id)
        builder.add("guard", guard.prov)
        if not guard.allowed:
            envelope, provenance = self._blocked(trace_id, builder, intent, mapped,
                                                 guard, workspace_id)
            return await self._finish(envelope, provenance, query, workspace_id, user_id,
                                      intent=intent.model_dump(mode="json"),
                                      allow_actions=allow_actions)

        # ── [4] retrieve ──────────────────────────────────────────────────
        retrieval = await self.retriever.execute(mapped, query, workspace_id, mode=mode)
        builder.add("retrieve", retrieval.prov)

        # ── [5] compose ───────────────────────────────────────────────────
        draft = await self.composer.compose(retrieval, query)
        builder.add("compose", draft.prov)

        # ── [6] gate ──────────────────────────────────────────────────────
        gated = await self.gate.validate(draft, mapped)
        builder.add("gate", gated.prov)

        tbox_version = self.catalog.snapshot_hash(workspace_id)
        provenance = builder.build(
            tbox_version=tbox_version, contract_ok=gated.contract_ok,
            citations=gated.citations,
        )
        violations = validate_provenance(
            provenance, resolver=self.resolver, expected_tbox_version=tbox_version
        )
        blocked_reasons = list(gated.blocked_reasons)
        contract_ok = gated.contract_ok
        if violations:
            contract_ok = False
            blocked_reasons.extend(
                f"PROVENANCE_{v.rule}_VIOLATION: {v.detail}" for v in violations
            )
            provenance = provenance.model_copy(update={"contract_ok": contract_ok})

        envelope = AnswerEnvelope(
            status=QaStatus.NO_ANSWER if draft.no_answer else QaStatus.ANSWERED,
            trace_id=trace_id,
            answer=None if draft.no_answer else gated.content,
            no_answer=draft.no_answer,
            no_answer_reason=draft.no_answer_reason or None,
            intent=intent,
            mapped_refs=mapped.object_types + mapped.relation_types + mapped.metrics,
            unmapped=mapped.unmapped,
            citations=gated.citations,
            suggested_actions=[],  # 由 _finish 派生并落库（F9，见 actions/）
            contract_ok=contract_ok,
            blocked_reasons=blocked_reasons,
            degraded=guard.degraded or bool(retrieval.degraded_engines),
            degraded_engines=list(retrieval.degraded_engines),
        )
        return await self._finish(envelope, provenance, query, workspace_id, user_id,
                                  intent=intent.model_dump(mode="json"),
                                  allow_actions=allow_actions)

    # ── 分支 ──────────────────────────────────────────────────────────────
    def _clarify(self, trace_id: str, builder: ProvenanceBuilder, intent, workspace_id: str,
                 query: str, user_id: str) -> Tuple[AnswerEnvelope, Provenance]:
        for step, component in (("map", "OntologyAligner"), ("guard", "RuleGuard"),
                                ("retrieve", "RetrievalExecutor"),
                                ("compose", "AnswerComposer")):
            builder.add(step, _decision(component, "decision:clarify_required"))
        builder.add("gate", _decision("OutputContractGate", "decision:clarify_required"))
        provenance = builder.build(tbox_version=self._safe_tbox_version(workspace_id),
                                   contract_ok=True, citations=[])
        envelope = AnswerEnvelope(
            status=QaStatus.CLARIFY,
            trace_id=trace_id,
            answer=None,
            intent=intent,
            clarify_question=intent.clarify_question,
            contract_ok=True,
            blocked_reasons=[],
        )
        return envelope, provenance

    def _blocked(self, trace_id: str, builder: ProvenanceBuilder, intent, mapped,
                 guard, workspace_id: str) -> Tuple[AnswerEnvelope, Provenance]:
        for step, component in (("retrieve", "RetrievalExecutor"),
                                ("compose", "AnswerComposer")):
            builder.add(step, _decision(component, "decision:skipped_after_block"))
        builder.add("gate", _decision("OutputContractGate", "decision:blocked_by_guard"))
        provenance = builder.build(tbox_version=self._safe_tbox_version(workspace_id),
                                   contract_ok=False, citations=[])
        envelope = AnswerEnvelope(
            status=QaStatus.BLOCKED,
            trace_id=trace_id,
            answer=None,
            intent=intent,
            mapped_refs=mapped.object_types + mapped.relation_types + mapped.metrics,
            unmapped=mapped.unmapped,
            contract_ok=False,
            blocked_reasons=list(guard.violations) or ["GUARD_DENIED"],
            degraded=guard.degraded,
        )
        return envelope, provenance

    def _safe_tbox_version(self, workspace_id: str) -> str:
        try:
            return self.catalog.snapshot_hash(workspace_id)
        except Exception as exc:  # noqa: BLE001 - 澄清/阻断路径不因 TBox 不可读而中断
            logger.warning("TBox snapshot hash unavailable: %s", exc)
            return ""

    # ── 落库 ──────────────────────────────────────────────────────────────
    async def _finish(self, envelope: AnswerEnvelope, provenance: Provenance, query: str,
                      workspace_id: str, user_id: str, intent: Dict[str, Any],
                      allow_actions: bool = False
                      ) -> Tuple[AnswerEnvelope, Provenance]:
        from datetime import datetime, timezone

        trace = {
            "trace_id": provenance.trace_id,
            "query": query,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "intent": intent,
            "degraded": envelope.degraded,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted = True
        try:
            self.trace_repo.save(trace, provenance)
        except Exception as exc:  # noqa: BLE001 - 溯源落库失败必须显式暴露
            persisted = False
            logger.error(
                "qa trace persist failed: trace_id=%s error_type=%s error=%s",
                provenance.trace_id, type(exc).__name__, exc,
            )
            envelope.degraded = True
            envelope.blocked_reasons = list(envelope.blocked_reasons) + [
                f"PROVENANCE_PERSIST_FAILED: {type(exc).__name__}: {exc}"
            ]
        if persisted:
            self._attach_actions(envelope, query, workspace_id, allow_actions)
        return envelope, provenance

    def _attach_actions(self, envelope: AnswerEnvelope, query: str, workspace_id: str,
                        allow_actions: bool) -> None:
        """派生并落库建议动作（AC-40/AC-42）；落库失败不掩盖，记入 blocked_reasons。"""
        actions = derive_actions(
            trace_id=envelope.trace_id,
            query=query,
            workspace_id=workspace_id,
            citation_count=len(envelope.citations),
            unmapped=envelope.unmapped,
            no_answer=envelope.no_answer,
            allow_actions=allow_actions,
        )
        try:
            envelope.suggested_actions = self.action_service.propose(
                envelope.trace_id, actions
            )
        except Exception as exc:  # noqa: BLE001 - 动作落库失败必须可见，不静默丢
            logger.error(
                "qa action persist failed: trace_id=%s error_type=%s error=%s",
                envelope.trace_id, type(exc).__name__, exc,
            )
            envelope.degraded = True
            envelope.blocked_reasons = list(envelope.blocked_reasons) + [
                f"ACTION_PERSIST_FAILED: {type(exc).__name__}: {exc}"
            ]


__all__ = ["QaPipeline", "CONFIDENCE_THRESHOLD"]
