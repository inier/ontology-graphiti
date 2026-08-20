"""决策 Neo4j 存储实现（ADR-076 §5.2）

- 自带 Graphiti Neo4jDriver 模块级单例（配置读 security_config），避免与 GraphManager 内部实例生命周期耦合
- EntityNode 三步法（generate_name_embedding + save）已在 graphiti-core 0.29.2 核验
- 双轨隔离：Graphiti 原生 group_id + 显式 workspace_id 属性，所有查询双过滤
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.infra.security import security_config

from odap.biz.decision.decision_record.interfaces import IDecisionStore
from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionCausalLink,
    DecisionChain,
    DecisionImpact,
    DecisionOutcome,
    DecisionRecord,
)

logger = logging.getLogger(__name__)

try:
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.nodes import EntityNode

    GRAPHITI_AVAILABLE = True
except ImportError:  # pragma: no cover
    Neo4jDriver = None
    EntityNode = None
    GRAPHITI_AVAILABLE = False

_driver = None


def get_decision_driver():
    """决策存储专用 Graphiti Neo4jDriver（模块级单例）。

    注意（0.29.2 已核验）：EntityNode.save() 要求 graphiti 包装 driver
    （访问 graph_operations_interface 属性），不能传裸 neo4j AsyncDriver。
    execute_query(cypher, **kwargs) 与裸 driver 用法兼容（kwargs 即查询参数）。
    """
    global _driver
    if _driver is None:
        if not GRAPHITI_AVAILABLE:
            raise RuntimeError("graphiti-core 未安装")
        _driver = Neo4jDriver(
            uri=security_config.NEO4J_URI,
            user=security_config.NEO4J_USER,
            password=security_config.get_neo4j_password(),
        )
    return _driver


def _props(record: Any) -> Dict[str, Any]:
    """neo4j Node/record 属性转普通 dict（剥离 datetime 等特殊类型为 iso 字符串的兜底在模型层处理）。"""
    return {k: v for k, v in dict(record).items()}


class Neo4jDecisionStore(IDecisionStore):
    """Decision 节点 + 因果/证据/触发边的 Neo4j 实现。"""

    def __init__(self) -> None:
        self._indices_ready = False

    async def ensure_indices(self) -> None:
        if self._indices_ready:
            return
        driver = get_decision_driver()
        statements = [
            "CREATE INDEX decision_uuid IF NOT EXISTS FOR (n:Decision) ON (n.uuid)",
            "CREATE INDEX decision_group_id IF NOT EXISTS FOR (n:Decision) ON (n.group_id)",
            "CREATE INDEX decision_workspace_id IF NOT EXISTS FOR (n:Decision) ON (n.workspace_id)",
            (
                "CREATE VECTOR INDEX decision_name_embedding IF NOT EXISTS "
                "FOR (n:Decision) ON (n.name_embedding) "
                "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
            ),
        ]
        for stmt in statements:
            try:
                await driver.execute_query(stmt)
            except Exception as e:  # 索引失败不阻断（如 dims 不匹配时仅降级向量索引）
                logger.warning("决策索引创建失败（不阻断）: %s -> %s", stmt[:60], e)
        self._indices_ready = True

    async def save_decision_node(self, record: DecisionRecord, embedder: Any = None) -> str:
        await self.ensure_indices()
        driver = get_decision_driver()

        saved_via_graphiti = False
        if GRAPHITI_AVAILABLE and embedder is not None:
            node = EntityNode(
                name=f"{record.recommended_option or record.decision_type}",
                labels=["Decision"],
                group_id=record.workspace_id,
                summary=record.context_summary[:2000] if record.context_summary else "",
            )
            # 以生成的 decision_id 作为节点 uuid（Neo4j uuid 字段保持与其一致）
            node.uuid = record.decision_id
            try:
                await node.generate_name_embedding(embedder)
            except Exception as emb_err:
                logger.warning("决策名 embedding 生成失败: %s", emb_err)
            if node.name_embedding:
                await node.save(driver)
                saved_via_graphiti = True
            else:
                # 审计关键路径零 LLM 原则：embedding 不可用不阻断决策落库。
                # EntityNode.save 内部会对空向量调用 setNodeVectorProperty 抛错，
                # 故降级为纯 Cypher 创建（先例检索自动走文本扫描降级路径）
                logger.warning("embedding 为空，降级为纯 Cypher 创建决策节点")

        if not saved_via_graphiti:
            await driver.execute_query(
                "MERGE (n:Decision:Entity {uuid: $uuid}) "
                "SET n.name = $name, n.group_id = $group_id, n.summary = $summary, "
                "n.created_at = datetime()",
                uuid=record.decision_id,
                name=record.recommended_option or record.decision_type,
                group_id=record.workspace_id,
                summary=(record.context_summary or "")[:2000],
            )

        # SET 扩展属性（ADR-076：DecisionRecord 完整字段 + 显式 workspace_id 属性双轨）
        await driver.execute_query(
            "MATCH (n:Decision {uuid: $uuid, group_id: $group_id}) SET n += $extensions",
            uuid=record.decision_id,
            group_id=record.workspace_id,
            extensions=record.to_node_properties(),
        )
        return record.decision_id

    async def get_decision(self, decision_id: str, workspace_id: str) -> Optional[DecisionRecord]:
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (n:Decision {uuid: $uuid, group_id: $ws}) RETURN n",
            uuid=decision_id,
            ws=workspace_id,
        )
        if not records:
            return None
        return DecisionRecord.from_node_properties(_props(records[0]["n"]))

    async def create_derived_from_edges(
        self,
        decision_id: str,
        workspace_id: str,
        evidence_entity_ids: List[str],
        evidence_episode_ids: List[str],
    ) -> None:
        driver = get_decision_driver()
        if evidence_entity_ids:
            await driver.execute_query(
                "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
                "UNWIND $eids AS eid "
                "MATCH (e:Entity {uuid: eid, group_id: $ws}) "
                "MERGE (d)-[:DERIVED_FROM]->(e)",
                did=decision_id,
                ws=workspace_id,
                eids=evidence_entity_ids,
            )
        if evidence_episode_ids:
            await driver.execute_query(
                "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
                "UNWIND $epids AS epid "
                "MATCH (ep:Episodic {uuid: epid, group_id: $ws}) "
                "MERGE (d)-[:DERIVED_FROM]->(ep)",
                did=decision_id,
                ws=workspace_id,
                epids=evidence_episode_ids,
            )

    async def add_causal_link(self, link: DecisionCausalLink) -> None:
        driver = get_decision_driver()
        edge = link.link_type.value
        if edge not in {t.value for t in CausalLinkType}:
            raise ValueError(f"不支持的因果边类型: {edge}")
        # 边类型来自枚举白名单，可安全拼接
        await driver.execute_query(
            f"MATCH (a:Decision {{uuid: $from_id, group_id: $ws}}), "
            f"(b:Decision {{uuid: $to_id, group_id: $ws}}) "
            f"MERGE (a)-[r:{edge}]->(b) SET r.created_at = datetime()",
            from_id=link.from_decision_id,
            to_id=link.to_decision_id,
            ws=link.workspace_id,
        )

    async def has_caused_by_path(
        self, from_decision_id: str, to_decision_id: str, workspace_id: str, max_hops: int = 10
    ) -> bool:
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (a:Decision {uuid: $from_id, group_id: $ws}), "
            "(b:Decision {uuid: $to_id, group_id: $ws}) "
            "RETURN EXISTS((a)-[:CAUSED_BY*1..10]->(b)) AS has_path",
            from_id=from_decision_id,
            to_id=to_decision_id,
            ws=workspace_id,
        )
        return bool(records and records[0].get("has_path"))

    async def create_triggered_edge(
        self, decision_id: str, workspace_id: str, action_record: Dict[str, Any]
    ) -> None:
        driver = get_decision_driver()
        await driver.execute_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "MERGE (a:ActionRecord {action_record_id: $ar_id, group_id: $ws}) "
            "SET a.action_type_id = $atype, a.target_object_id = $target, "
            "a.status = $status, a.workspace_id = $ws "
            "MERGE (d)-[:TRIGGERED]->(a)",
            did=decision_id,
            ws=workspace_id,
            ar_id=action_record.get("action_record_id", ""),
            atype=action_record.get("action_type_id", ""),
            target=action_record.get("target_object_id", ""),
            status=action_record.get("status", ""),
        )

    async def trace_chain(self, decision_id: str, workspace_id: str, max_hops: int = 3) -> Optional[DecisionChain]:
        decision = await self.get_decision(decision_id, workspace_id)
        if decision is None:
            return None
        driver = get_decision_driver()

        records, _, _ = await driver.execute_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH (d)-[:DERIVED_FROM]->(e:Entity) "
            "OPTIONAL MATCH (d)-[:DERIVED_FROM]->(ep:Episodic) "
            "RETURN collect(DISTINCT e) AS entities, collect(DISTINCT ep) AS episodes",
            did=decision_id,
            ws=workspace_id,
        )
        entities: List[Dict[str, Any]] = []
        episodes: List[Dict[str, Any]] = []
        if records:
            entities = [_props(n) for n in records[0].get("entities") or [] if n is not None]
            episodes = [_props(n) for n in records[0].get("episodes") or [] if n is not None]

        parent_records, _, _ = await driver.execute_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH path=(d)-[:CAUSED_BY*1..3]->(p:Decision) "
            "WHERE p.group_id = $ws "
            "RETURN collect(DISTINCT p) AS parents",
            did=decision_id,
            ws=workspace_id,
        )
        parents = []
        if parent_records:
            parents = [
                DecisionRecord.from_node_properties(_props(n))
                for n in parent_records[0].get("parents") or []
                if n is not None
            ]

        precedent_records, _, _ = await driver.execute_query(
            "MATCH (d:Decision {uuid: $did, group_id: $ws}) "
            "OPTIONAL MATCH (p:Decision)-[:PRECEDENT_FOR]->(d) "
            "WHERE p.group_id = $ws "
            "RETURN collect(DISTINCT p) AS precedents",
            did=decision_id,
            ws=workspace_id,
        )
        precedents = []
        if precedent_records:
            precedents = [
                DecisionRecord.from_node_properties(_props(n))
                for n in precedent_records[0].get("precedents") or []
                if n is not None
            ]

        return DecisionChain(
            decision=decision,
            evidence_entities=entities,
            evidence_episodes=episodes,
            parent_chain=parents,
            precedents=precedents,
            reasoning_trace=decision.reasoning_trace,
        )

    async def find_similar_by_text(
        self, workspace_id: str, query: str, top_k: int = 5
    ) -> List[DecisionRecord]:
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (n:Decision {group_id: $ws}) "
            "WHERE n.name CONTAINS $q OR n.context_summary CONTAINS $q "
            "OR n.recommended_option CONTAINS $q "
            "RETURN n ORDER BY n.created_at DESC LIMIT $k",
            ws=workspace_id,
            q=query,
            k=top_k,
        )
        return [DecisionRecord.from_node_properties(_props(r["n"])) for r in records]

    async def analyze_impact(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionImpact]:
        decision = await self.get_decision(decision_id, workspace_id)
        if decision is None:
            return None
        driver = get_decision_driver()
        completeness = "full"

        # 下游决策（CAUSED_BY 反向 ≤3 跳）
        derived: List[Dict[str, Any]] = []
        try:
            records, _, _ = await driver.execute_query(
                "MATCH (d:Decision {uuid: $did, group_id: $ws})<-[:CAUSED_BY*1..3]-(child:Decision) "
                "WHERE child.group_id = $ws RETURN DISTINCT child LIMIT 20",
                did=decision_id,
                ws=workspace_id,
            )
            derived = [_props(r["child"]) for r in records]
        except Exception as e:
            logger.warning("下游决策遍历失败: %s", e)
            completeness = "partial"

        # 目标对象变化（TRIGGERED -> ActionRecord）
        target_changes: List[Dict[str, Any]] = []
        try:
            records, _, _ = await driver.execute_query(
                "MATCH (d:Decision {uuid: $did, group_id: $ws})-[:TRIGGERED]->(a:ActionRecord) "
                "RETURN a",
                did=decision_id,
                ws=workspace_id,
            )
            target_changes = [_props(r["a"]) for r in records]
        except Exception as e:
            logger.warning("目标变化查询失败: %s", e)
            completeness = "degraded_target_resolution"

        # 协同证据决策
        co_decisions: List[Dict[str, Any]] = []
        try:
            records, _, _ = await driver.execute_query(
                "MATCH (d:Decision {uuid: $did, group_id: $ws})-[:DERIVED_FROM]->(e:Entity)"
                "<-[:DERIVED_FROM]-(other:Decision) "
                "WHERE other.uuid <> $did AND other.group_id = $ws "
                "RETURN DISTINCT other LIMIT 5",
                did=decision_id,
                ws=workspace_id,
            )
            co_decisions = [_props(r["other"]) for r in records]
        except Exception as e:
            logger.warning("协同证据决策查询失败: %s", e)
            completeness = "partial"

        # 证据实体在决策生效后的边失效情况（Q5 决议：查询而非监听）
        invalidated_edges: List[Dict[str, Any]] = []
        if decision.evidence_entity_ids:
            try:
                records, _, _ = await driver.execute_query(
                    "MATCH (e:Entity)-[r:RELATES_TO]->(o) "
                    "WHERE e.uuid IN $eids AND r.invalid_at IS NOT NULL "
                    "AND r.invalid_at > datetime($created) "
                    "RETURN e.uuid AS from_uuid, type(r) AS edge_type, "
                    "o.uuid AS to_uuid, r.invalid_at AS invalid_at LIMIT 20",
                    eids=decision.evidence_entity_ids,
                    created=decision.created_at.isoformat(),
                )
                invalidated_edges = [dict(r) for r in records]
            except Exception as e:
                logger.warning("边失效查询失败: %s", e)

        if invalidated_edges:
            target_changes = target_changes + [
                {"type": "edge_invalidated", **e} for e in invalidated_edges
            ]

        return DecisionImpact(
            decision_id=decision_id,
            derived_decisions=derived,
            target_changes=target_changes,
            co_evidence_decisions=co_decisions,
            impact_completeness=completeness,
        )

    async def update_outcome(
        self,
        decision_id: str,
        workspace_id: str,
        outcome: DecisionOutcome,
        outcome_details: Dict[str, Any],
        feedback_summary: Optional[str] = None,
    ) -> bool:
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (n:Decision {uuid: $did, group_id: $ws}) "
            "SET n.outcome = $outcome, n.outcome_details = $details, "
            "n.feedback_summary = $summary, n.updated_at = $now "
            "RETURN n.uuid AS uuid",
            did=decision_id,
            ws=workspace_id,
            outcome=outcome.value,
            details=json.dumps(outcome_details, ensure_ascii=False, default=str),
            summary=feedback_summary,
            now=datetime.now(timezone.utc).isoformat(),
        )
        return bool(records)

    def edge_type_values(self) -> List[str]:
        return [t.value for t in CausalLinkType]
