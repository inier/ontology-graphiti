"""F9 动作测试的公共夹具（非测试模块：仅供 test_qa_actions / test_qa_action_hitl 复用）。

动作必须挂在真实 trace 上（AC-42），因此这里落一条六步齐全的 trace 再派生动作，
不做「只构造 action 对象」的旁路。
"""

from __future__ import annotations

from typing import Any, List

from odap.biz.core.ontology.orchestration.actions.derive import derive_actions
from odap.biz.core.ontology.orchestration.contracts import (
    STEP_ORDER,
    StepProv,
    UnmappedSlot,
)

SEED_TRACE = "urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A"
USER = {"sub": "u-analyst", "role": "admin", "roles": ["admin"],
        "workspace_id": "ws-supply"}
QUERY = "2026Q3 订单退货率最高的三个品类"
UNMAPPED = [UnmappedSlot(slot="品类", raw="生鲜")]


def seed_trace(trace_repo, trace_id: str = SEED_TRACE) -> str:
    """写入一条六步齐全的 trace。"""
    from odap.biz.core.ontology.orchestration.provenance import ProvenanceBuilder

    builder = ProvenanceBuilder(trace_id)
    components = ["IntentRouter", "OntologyAligner", "RuleGuard",
                  "RetrievalExecutor", "AnswerComposer", "OutputContractGate"]
    for step, component in zip(STEP_ORDER, components):
        builder.add(step, StepProv(component=component))
    provenance = builder.build(tbox_version="sha256:seed", contract_ok=True, citations=[])
    trace_repo.save(
        {
            "trace_id": trace_id,
            "query": QUERY,
            "workspace_id": "ws-supply",
            "user_id": "u-analyst",
            "intent": {"intent_type": "metric_query"},
            "degraded": False,
            "created_at": "2026-10-17T00:00:00+00:00",
        },
        provenance,
    )
    return trace_id


def action_types(actions) -> List[str]:
    return [a.action_type for a in actions]


def build_actions(*, allow_actions: bool = True, citation_count: int = 1,
                  unmapped=None, no_answer: bool = False):
    return derive_actions(
        trace_id=SEED_TRACE, query=QUERY, citation_count=citation_count,
        unmapped=UNMAPPED if unmapped is None else unmapped,
        no_answer=no_answer, allow_actions=allow_actions,
    )


def propose_all(action_service, trace_repo, *, allow_actions: bool = True,
                citation_count: int = 1) -> List[Any]:
    """落 trace → 派生动作 → 入库，返回带 action_id 的动作列表。"""
    seed_trace(trace_repo)
    return action_service.propose(
        SEED_TRACE, build_actions(allow_actions=allow_actions, citation_count=citation_count),
    )


def propose_high_risk(action_service, trace_repo):
    """返回一条高风险动作（submit_gap_fill）。"""
    saved = propose_all(action_service, trace_repo)
    return next(a for a in saved if a.action_type == "submit_gap_fill")


__all__ = [
    "QUERY",
    "SEED_TRACE",
    "UNMAPPED",
    "USER",
    "action_types",
    "build_actions",
    "propose_all",
    "propose_high_risk",
    "seed_trace",
]
