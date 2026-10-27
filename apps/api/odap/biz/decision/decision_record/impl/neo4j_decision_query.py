"""决策读侧 Neo4j 实现（ADR-091 §5.2 / §5.5）

从 `neo4j_decision_store.py` 拆出的纯方法搬迁（408 行 -> 两个 <=300 行文件）。
写侧仍留原文件：读侧与写侧的生命周期、索引依赖、失败降级策略不同，
混在一个类里既越行数上限，也让"读到脏数据"与"写不进去"这两类问题难定位。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from odap.biz.decision.decision_record.impl import neo4j_driver
from odap.biz.decision.decision_record.impl.decision_query_cypher import (
    build_params,
    order_clause,
    where_clause,
)
from odap.biz.decision.decision_record.interfaces.decision_query import DecisionQuery
from odap.biz.decision.decision_record.models import (
    DecisionChain,
    DecisionImpact,
    DecisionRecord,
)

logger = logging.getLogger(__name__)

# 台账精确计数上限：Neo4j 精确 count 是全扫描，10 万级过滤计数不可接受。
# 超过探测上限即返回 (probe, True)，前端显示"约 N 条"并关闭"跳末页"。
COUNT_PROBE_LIMIT = 5000


class Neo4jDecisionQueryMixin:
    """`:Decision` 读侧：因果链 / 文本检索 / 影响分析 / 分页列表 / 计数。"""

    # ---------------- 因果链 ----------------

    async def trace_chain(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionChain]:
        decision = await self.get_decision(decision_id, workspace_id)
        if decision is None:
            return None
        entities, episodes = await self._chain_evidence(decision_id, workspace_id)
        return DecisionChain(
            decision=decision,
            evidence_entities=entities,
            evidence_episodes=episodes,
            parent_chain=await self._chain_parents(decision_id, workspace_id),
            precedents=await self._chain_precedents(decision_id, workspace_id),
            reasoning_trace=decision.reasoning_trace,
        )

    async def _chain_evidence(
        self, decision_id: str, workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH (d)-[:DERIVED_FROM]->(e:Entity) "
            "OPTIONAL MATCH (d)-[:DERIVED_FROM]->(ep:Episodic) "
            "RETURN collect(DISTINCT e) AS entities, collect(DISTINCT ep) AS episodes",
            did=decision_id,
            ws=workspace_id,
        )
        if not records:
            return [], []
        entities = [neo4j_driver.node_props(n) for n in records[0].get("entities") or [] if n]
        episodes = [neo4j_driver.node_props(n) for n in records[0].get("episodes") or [] if n]
        return entities, episodes

    async def _chain_related(
        self, cypher: str, key: str, decision_id: str, workspace_id: str
    ) -> List[DecisionRecord]:
        records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
            cypher, did=decision_id, ws=workspace_id
        )
        if not records:
            return []
        return [
            DecisionRecord.from_node_properties(neo4j_driver.node_props(n))
            for n in records[0].get(key) or []
            if n is not None
        ]

    async def _chain_parents(self, decision_id: str, workspace_id: str) -> List[DecisionRecord]:
        return await self._chain_related(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH path=(d)-[:CAUSED_BY*1..3]->(p:Decision) "
            "WHERE p.group_id = $ws "
            "RETURN collect(DISTINCT p) AS parents",
            "parents",
            decision_id,
            workspace_id,
        )

    async def _chain_precedents(self, decision_id: str, workspace_id: str) -> List[DecisionRecord]:
        return await self._chain_related(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH (p:Decision)-[:PRECEDENT_FOR]->(d) "
            "WHERE p.group_id = $ws "
            "RETURN collect(DISTINCT p) AS precedents",
            "precedents",
            decision_id,
            workspace_id,
        )

    # ---------------- 文本检索降级路径 ----------------

    async def find_similar_by_text(
        self, workspace_id: str, query: str, top_k: int = 5
    ) -> List[DecisionRecord]:
        records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
            "MATCH (n:Decision {group_id: $ws}) "
            "WHERE n.name CONTAINS $q OR n.context_summary CONTAINS $q "
            "OR n.recommended_option CONTAINS $q "
            "RETURN n ORDER BY n.created_at DESC LIMIT $k",
            ws=workspace_id,
            q=query,
            k=top_k,
        )
        return [
            DecisionRecord.from_node_properties(neo4j_driver.node_props(r["n"])) for r in records
        ]

    # ---------------- 影响分析 ----------------

    async def analyze_impact(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionImpact]:
        decision = await self.get_decision(decision_id, workspace_id)
        if decision is None:
            return None
        derived, partial_down = await self._impact_derived(decision_id, workspace_id)
        target_changes, degraded_target = await self._impact_targets(decision_id, workspace_id)
        co_decisions, partial_co = await self._impact_co_evidence(decision_id, workspace_id)
        invalidated = await self._impact_invalidated_edges(decision)

        if invalidated:
            target_changes = target_changes + [{"type": "edge_invalidated", **e} for e in invalidated]
        completeness = self._impact_completeness(
            partial_down, degraded_target, partial_co
        )
        return DecisionImpact(
            decision_id=decision_id,
            derived_decisions=derived,
            target_changes=target_changes,
            co_evidence_decisions=co_decisions,
            impact_completeness=completeness,
        )

    def _impact_completeness(
        self, partial_down: bool, degraded_target: bool, partial_co: bool
    ) -> str:
        if degraded_target:
            return "degraded_target_resolution"
        if partial_down or partial_co:
            return "partial"
        return "full"

    async def _impact_query(
        self, cypher: str, key: str, decision_id: str, workspace_id: str, tag: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """执行单条影响分析子查询；失败返回 ([], True) 表示该段不完整。"""
        try:
            records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
                cypher, did=decision_id, ws=workspace_id
            )
            return [neo4j_driver.node_props(r[key]) for r in records], False
        except Exception as e:  # 单段失败只降级完整性标注，不整体失败
            logger.warning("%s查询失败: %s", tag, e)
            return [], True

    async def _impact_derived(
        self, decision_id: str, workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        return await self._impact_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws})<-[:CAUSED_BY*1..3]-(child:Decision) "
            "WHERE child.group_id = $ws RETURN DISTINCT child LIMIT 20",
            "child",
            decision_id,
            workspace_id,
            "下游决策遍历",
        )

    async def _impact_targets(
        self, decision_id: str, workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        return await self._impact_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws})-[:TRIGGERED]->(a:ActionRecord) RETURN a",
            "a",
            decision_id,
            workspace_id,
            "目标变化",
        )

    async def _impact_co_evidence(
        self, decision_id: str, workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        return await self._impact_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws})-[:DERIVED_FROM]->(e:Entity)"
            "<-[:DERIVED_FROM]-(other:Decision) "
            "WHERE other.uuid <> $did AND other.group_id = $ws "
            "RETURN DISTINCT other LIMIT 5",
            "other",
            decision_id,
            workspace_id,
            "协同证据决策",
        )

    async def _impact_invalidated_edges(
        self, decision: DecisionRecord
    ) -> List[Dict[str, Any]]:
        """证据实体在决策生效后的边失效情况（Q5 决议：查询而非监听）。"""
        if not decision.evidence_entity_ids:
            return []
        try:
            records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
                "MATCH (e:Entity)-[r:RELATES_TO]->(o) "
                "WHERE e.uuid IN $eids AND r.invalid_at IS NOT NULL "
                "AND r.invalid_at > datetime($created) "
                "RETURN e.uuid AS from_uuid, type(r) AS edge_type, "
                "o.uuid AS to_uuid, r.invalid_at AS invalid_at LIMIT 20",
                eids=decision.evidence_entity_ids,
                created=decision.created_at.isoformat(),
            )
            return [dict(r) for r in records]
        except Exception as e:
            logger.warning("边失效查询失败: %s", e)
            return []

    # ---------------- 台账分页与计数 ----------------

    async def list_decisions(
        self, query: DecisionQuery, skip: int = 0, limit: int = 20
    ) -> List[DecisionRecord]:
        """台账/队列分页列表。MATCH 恒带 `group_id = $ws`（隔离双保险）。"""
        params = build_params(query)
        cypher = (
            "MATCH (n:Decision {group_id: $ws}) "
            f"WHERE {where_clause(query.time_field)} "
            f"RETURN n ORDER BY {order_clause(query.sort_by, query.order)} "
            "SKIP $skip LIMIT $limit"
        )
        records, _, _ = await neo4j_driver.get_decision_driver().execute_query(
            cypher, **params, skip=skip, limit=limit
        )
        return [
            DecisionRecord.from_node_properties(neo4j_driver.node_props(r["n"])) for r in records
        ]

    async def count_decisions(
        self, query: DecisionQuery, probe: int = COUNT_PROBE_LIMIT
    ) -> Tuple[int, bool]:
        """返回 (count, is_estimate)。`probe<=0` 表示要精确值（队列四计数用）。

        估算路径用 `WITH n LIMIT probe+1 RETURN count(n)`：命中上限即判估算，
        避免在大表上做全量 count（10 万级过滤计数不可接受）。
        """
        params = build_params(query)
        driver = neo4j_driver.get_decision_driver()
        if probe and probe > 0:
            cypher = (
                "MATCH (n:Decision {group_id: $ws}) "
                f"WHERE {where_clause(query.time_field)} WITH n LIMIT $cap RETURN count(n) AS c"
            )
            records, _, _ = await driver.execute_query(cypher, **params, cap=probe + 1)
            found = int(records[0]["c"]) if records else 0
            if found > probe:
                return probe, True
            return found, False

        cypher = (
            "MATCH (n:Decision {group_id: $ws}) "
            f"WHERE {where_clause(query.time_field)} RETURN count(n) AS c"
        )
        records, _, _ = await driver.execute_query(cypher, **params)
        return (int(records[0]["c"]) if records else 0), False
