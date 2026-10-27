"""决策读侧测试替身（内存版 `IDecisionStore`）

筛选 / 排序 / 分页语义与 Neo4j 实现保持一致，使"分组与计数同源"这类
契约级不变量可在无数据库环境下断言。
"""

from datetime import datetime

from odap.biz.decision.decision_record.interfaces import DecisionQuery, IDecisionStore
from odap.biz.decision.decision_record.models import CausalLinkType, DecisionRecord


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _decided_at(record: DecisionRecord):
    """`resolution.at`（缺省/不可解析返回 None），与真实实现的 `decided_at` 派生一致。"""
    resolution = record.resolution
    if not isinstance(resolution, dict):
        return None
    try:
        parsed = datetime.fromisoformat(str(resolution.get("at")))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=record.created_at.tzinfo)


def _time_getter(field: str):
    """按 `time_field` 取时间列；`decided_at` 缺值回落 `updated_at`（同 Cypher 的 coalesce）。"""
    if field == "updated_at":
        return lambda r: r.updated_at  # noqa: E731
    if field == "decided_at":
        return lambda r: _decided_at(r) or r.updated_at  # noqa: E731
    return lambda r: r.created_at  # noqa: E731


class InMemoryDecisionStore(IDecisionStore):
    def __init__(self, records=None) -> None:
        self.records = list(records or [])
        self.list_calls = []
        self.count_calls = []
        self.ensure_calls = 0

    async def ensure_indices(self) -> None:
        self.ensure_calls += 1

    async def save_decision_node(self, record: DecisionRecord, embedder=None) -> str:
        self.records.append(record)
        return record.decision_id

    async def get_decision(self, decision_id: str, workspace_id: str):
        for record in self.records:
            if record.decision_id == decision_id and record.workspace_id == workspace_id:
                return record
        return None

    async def create_derived_from_edges(self, *args, **kwargs) -> None:
        return None

    async def add_causal_link(self, link) -> None:
        return None

    async def has_caused_by_path(self, *args, **kwargs) -> bool:
        return False

    async def create_triggered_edge(self, *args, **kwargs) -> None:
        return None

    async def trace_chain(self, *args, **kwargs):
        return None

    async def find_similar_by_text(self, *args, **kwargs):
        return []

    async def analyze_impact(self, *args, **kwargs):
        return None

    async def update_outcome(self, *args, **kwargs) -> bool:
        return True

    def edge_type_values(self):
        return [t.value for t in CausalLinkType]

    # ---- 台账/队列依赖的方法 ----

    def _filtered(self, query: DecisionQuery):
        rows = [r for r in self.records if r.workspace_id == query.workspace_id]
        if query.statuses:
            rows = [r for r in rows if r.status.value in query.statuses]
        if query.outcomes:
            rows = [r for r in rows if r.outcome.value in query.outcomes]
        if query.entry_source:
            rows = [r for r in rows if r.entry_source.value == query.entry_source]
        if query.decision_type:
            rows = [r for r in rows if r.decision_type == query.decision_type]
        if query.agent_id:
            rows = [r for r in rows if r.agent_id == query.agent_id]
        if query.min_confidence is not None:
            rows = [r for r in rows if r.confidence >= query.min_confidence]
        if query.max_confidence is not None:
            rows = [r for r in rows if r.confidence <= query.max_confidence]
        if query.exclude_assumed:
            rows = [r for r in rows if not r.status_assumed]
        if query.text_query:
            rows = [
                r
                for r in rows
                if query.text_query in r.context_summary
                or query.text_query in r.recommended_option
            ]
        stamp = _time_getter(query.time_field)
        if query.created_from:
            rows = [r for r in rows if stamp(r) >= _dt(query.created_from)]
        if query.created_to:
            rows = [r for r in rows if stamp(r) <= _dt(query.created_to)]
        return rows

    async def list_decisions(self, query: DecisionQuery, skip: int = 0, limit: int = 20):
        self.list_calls.append((query, skip, limit))
        rows = self._sorted(self._filtered(query), query)
        return rows[skip : skip + limit]

    async def count_decisions(self, query: DecisionQuery, probe: int = 5000):
        self.count_calls.append((query, probe))
        total = len(self._filtered(query))
        if probe and probe > 0 and total > probe:
            return probe, True
        return total, False

    def _sorted(self, rows, query: DecisionQuery):
        if query.sort_by == "evidence_count":
            key = lambda r: len(r.evidence_entity_ids)  # noqa: E731
        elif query.sort_by == "confidence":
            key = lambda r: r.confidence  # noqa: E731
        elif query.sort_by == "updated_at":
            key = lambda r: r.updated_at  # noqa: E731
        else:
            key = lambda r: r.created_at  # noqa: E731
        return sorted(rows, key=key, reverse=query.order == "desc")
