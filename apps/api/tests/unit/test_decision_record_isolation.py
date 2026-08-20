"""ADR-076 决策智能：工作空间隔离与因果边规则单元测试

使用 FakeDecisionStore（内存实现 IDecisionStore），不依赖 Neo4j/Graphiti 连接。
覆盖 ADR-076 §7 隔离 Checklist 的核心规则：
- workspace_id 非空强制（record / similar / causal-link / check-rules）
- 读写携带 decision_id AND workspace_id 双条件
- 因果边两端同空间校验 + CAUSED_BY 环检测
- outcome 回填双条件更新
"""

from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

from odap.biz.decision.decision_record.interfaces import IDecisionStore
from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionCausalLink,
    DecisionOutcome,
    DecisionRecord,
)
from odap.biz.decision.decision_record.services import DecisionService
from odap.infra.security.workspace_access import get_current_workspace


class FakeDecisionStore(IDecisionStore):
    """内存版决策存储，记录全部调用参数用于隔离断言。"""

    def __init__(self) -> None:
        self.nodes: Dict[str, DecisionRecord] = {}
        self.links: List[DecisionCausalLink] = []
        self.calls: List[tuple] = []
        self.cycle_exists = False

    async def ensure_indices(self) -> None:
        pass

    async def save_decision_node(self, record: DecisionRecord, embedder: Any = None) -> str:
        self.calls.append(("save", record.decision_id, record.workspace_id))
        self.nodes[record.decision_id] = record
        return record.decision_id

    async def get_decision(self, decision_id: str, workspace_id: str) -> Optional[DecisionRecord]:
        self.calls.append(("get", decision_id, workspace_id))
        rec = self.nodes.get(decision_id)
        if rec is None or rec.workspace_id != workspace_id:
            return None  # 双条件：workspace 不匹配视同不存在
        return rec

    async def create_derived_from_edges(self, decision_id, workspace_id, eids, epids) -> None:
        self.calls.append(("derived_from", decision_id, workspace_id))

    async def add_causal_link(self, link: DecisionCausalLink) -> None:
        self.calls.append(("causal_link", link.from_decision_id, link.workspace_id))
        self.links.append(link)

    async def has_caused_by_path(self, from_id, to_id, workspace_id, max_hops: int = 10) -> bool:
        return self.cycle_exists

    async def create_triggered_edge(self, decision_id, workspace_id, action_record) -> None:
        self.calls.append(("triggered", decision_id, workspace_id))

    async def trace_chain(self, decision_id, workspace_id, max_hops: int = 3):
        return None

    async def find_similar_by_text(self, workspace_id, query, top_k: int = 5):
        self.calls.append(("similar_text", workspace_id, query))
        return [r for r in self.nodes.values() if r.workspace_id == workspace_id][:top_k]

    async def analyze_impact(self, decision_id, workspace_id, max_hops: int = 3):
        return None

    async def update_outcome(self, decision_id, workspace_id, outcome, outcome_details, feedback_summary=None) -> bool:
        self.calls.append(("update_outcome", decision_id, workspace_id, outcome))
        rec = await self.get_decision(decision_id, workspace_id)
        if rec is None:
            return False
        rec.outcome = outcome
        return True

    def edge_type_values(self) -> List[str]:
        return [t.value for t in CausalLinkType]


@pytest.fixture
def store() -> FakeDecisionStore:
    return FakeDecisionStore()


@pytest.fixture
def service(store: FakeDecisionStore) -> DecisionService:
    return DecisionService(store=store)


def _record(ws: str, **kwargs) -> DecisionRecord:
    return DecisionRecord(workspace_id=ws, context_summary="测试决策", **kwargs)


# ---------------- 非空强制 ----------------


@pytest.mark.asyncio
async def test_record_decision_rejects_empty_workspace(service: DecisionService):
    with pytest.raises(ValueError, match="workspace_id"):
        await service.record_decision(_record(""))


@pytest.mark.asyncio
async def test_find_similar_rejects_empty_workspace(service: DecisionService):
    with pytest.raises(ValueError, match="workspace_id"):
        await service.find_similar_decisions("", "查询")


@pytest.mark.asyncio
async def test_causal_link_rejects_empty_workspace(service: DecisionService):
    with pytest.raises(ValueError, match="workspace_id"):
        await service.add_causal_relationship("a", "b", CausalLinkType.CAUSED_BY, "")


@pytest.mark.asyncio
async def test_check_rules_rejects_empty_workspace(service: DecisionService):
    with pytest.raises(ValueError, match="workspace_id"):
        await service.check_decision_rules("", user={}, action="a", resource={})


# ---------------- 双条件读写 ----------------


@pytest.mark.asyncio
async def test_record_then_read_carries_workspace(service: DecisionService, store: FakeDecisionStore):
    rec = await service.record_decision(_record("ws-a"))
    assert ("save", rec.decision_id, "ws-a") in store.calls
    # 跨空间读取 → None（双条件不命中）
    assert await store.get_decision(rec.decision_id, "ws-b") is None
    assert await store.get_decision(rec.decision_id, "ws-a") is not None


@pytest.mark.asyncio
async def test_update_outcome_requires_matching_workspace(service: DecisionService, store: FakeDecisionStore):
    rec = await service.record_decision(_record("ws-a"))
    ok = await service.update_decision_outcome(
        rec.decision_id, "ws-b", DecisionOutcome.SUCCESS, {}
    )
    assert ok is False  # 跨空间更新被拒绝（返回 False → 路由层 404）
    ok = await service.update_decision_outcome(
        rec.decision_id, "ws-a", DecisionOutcome.SUCCESS, {}
    )
    assert ok is True


@pytest.mark.asyncio
async def test_find_similar_falls_back_with_workspace(service: DecisionService, store: FakeDecisionStore):
    await service.record_decision(_record("ws-a"))
    await service.record_decision(_record("ws-b"))
    results = await service.find_similar_decisions("ws-a", "测试决策")
    assert all(r.workspace_id == "ws-a" for r in results)


# ---------------- 因果边规则 ----------------


@pytest.mark.asyncio
async def test_causal_link_requires_same_workspace(service: DecisionService, store: FakeDecisionStore):
    a = await service.record_decision(_record("ws-a"))
    b = await service.record_decision(_record("ws-b"))
    with pytest.raises(ValueError, match="同一工作空间"):
        await service.add_causal_relationship(
            a.decision_id, b.decision_id, CausalLinkType.INFLUENCED_BY, "ws-a"
        )


@pytest.mark.asyncio
async def test_causal_link_cycle_detection(service: DecisionService, store: FakeDecisionStore):
    a = await service.record_decision(_record("ws-a"))
    b = await service.record_decision(_record("ws-a"))
    store.cycle_exists = True
    with pytest.raises(ValueError, match="禁止成环"):
        await service.add_causal_relationship(
            a.decision_id, b.decision_id, CausalLinkType.CAUSED_BY, "ws-a"
        )


@pytest.mark.asyncio
async def test_causal_link_happy_path(service: DecisionService, store: FakeDecisionStore):
    a = await service.record_decision(_record("ws-a"))
    b = await service.record_decision(_record("ws-a"))
    link = await service.add_causal_relationship(
        a.decision_id, b.decision_id, CausalLinkType.PRECEDENT_FOR, "ws-a"
    )
    assert link.link_type == CausalLinkType.PRECEDENT_FOR
    assert link.workspace_id == "ws-a"


@pytest.mark.asyncio
async def test_precedent_ids_auto_trace(service: DecisionService, store: FakeDecisionStore):
    precedent = await service.record_decision(_record("ws-a"))
    rec = _record("ws-a")
    rec.precedent_decision_ids = [precedent.decision_id]
    await service.record_decision(rec)
    precedent_links = [l for l in store.links if l.link_type == CausalLinkType.PRECEDENT_FOR]
    assert len(precedent_links) == 1
    assert precedent_links[0].from_decision_id == precedent.decision_id
    assert precedent_links[0].to_decision_id == rec.decision_id


# ---------------- get_current_workspace 依赖 ----------------


@pytest.mark.asyncio
async def test_get_current_workspace_from_ws_id():
    ws = await get_current_workspace({"sub": "u1", "role": "member", "ws_id": "ws-test"})
    assert ws == "ws-test"


@pytest.mark.asyncio
async def test_get_current_workspace_rejects_missing_claim():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_workspace({"sub": "u1", "role": "member"})
    assert exc_info.value.status_code == 422
