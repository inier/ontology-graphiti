"""决策 Neo4j 存储实现（ADR-076 §5.2 / ADR-101 §5.6）

- 自带 Graphiti Neo4jDriver 模块级单例（见 `neo4j_driver`），避免与 GraphManager 内部实例生命周期耦合
- EntityNode 三步法（generate_name_embedding + save）已在 graphiti-core 0.29.2 核验
- 双轨隔离：Graphiti 原生 group_id + 显式 workspace_id 属性，所有查询双过滤
- 本文件只保留**写侧**；读侧在 `neo4j_decision_query`，存量迁移在 `neo4j_decision_migration`
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.decision.decision_record.impl import neo4j_driver
from odap.biz.decision.decision_record.impl.neo4j_decision_migration import (
    Neo4jDecisionMigrationMixin,
)
from odap.biz.decision.decision_record.impl.neo4j_decision_query import (
    Neo4jDecisionQueryMixin,
)
from odap.biz.decision.decision_record.interfaces import IDecisionStore
from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionCausalLink,
    DecisionOutcome,
    DecisionRecord,
    StatusOutcomePatch,
)

logger = logging.getLogger(__name__)

# 兼容既有导入路径（`from ...impl.neo4j_decision_store import get_decision_driver`）
get_decision_driver = neo4j_driver.get_decision_driver

_INDEX_STATEMENTS = [
    "CREATE INDEX decision_uuid IF NOT EXISTS FOR (n:Decision) ON (n.uuid)",
    "CREATE INDEX decision_group_id IF NOT EXISTS FOR (n:Decision) ON (n.group_id)",
    "CREATE INDEX decision_workspace_id IF NOT EXISTS FOR (n:Decision) ON (n.workspace_id)",
    # 台账默认视图（group_id + created_at 倒序）：没有它就是全 label 扫描
    "CREATE INDEX decision_ws_created IF NOT EXISTS "
    "FOR (n:Decision) ON (n.group_id, n.created_at)",
    "CREATE INDEX decision_ws_status_created IF NOT EXISTS "
    "FOR (n:Decision) ON (n.group_id, n.status, n.created_at)",
    "CREATE INDEX decision_ws_entry IF NOT EXISTS FOR (n:Decision) ON (n.group_id, n.entry_source)",
    "CREATE INDEX decision_ws_agent IF NOT EXISTS FOR (n:Decision) ON (n.group_id, n.agent_id)",
    (
        "CREATE VECTOR INDEX decision_name_embedding IF NOT EXISTS "
        "FOR (n:Decision) ON (n.name_embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
    ),
]


class Neo4jDecisionStore(Neo4jDecisionMigrationMixin, Neo4jDecisionQueryMixin, IDecisionStore):
    """Decision 节点 + 因果/证据/触发边的 Neo4j 实现（写侧 + 索引 + 迁移）。"""

    def __init__(self) -> None:
        self._indices_ready = False

    async def ensure_indices(self) -> None:
        """幂等创建索引，并顺带跑一次存量迁移（读侧自愈入口）。"""
        if self._indices_ready:
            return
        driver = get_decision_driver()
        for stmt in _INDEX_STATEMENTS:
            try:
                await driver.execute_query(stmt)
            except Exception as e:  # 索引失败不阻断（如 dims 不匹配时仅降级向量索引）
                logger.warning("决策索引创建失败（不阻断）: %s -> %s", stmt[:60], e)
        try:
            stats = await self.migrate_legacy_fields()
            if stats["migrated_status"] or stats["migrated_evidence_count"]:
                logger.info("决策存量迁移完成: %s", stats)
        except Exception as e:  # 迁移失败不阻断索引就绪（下次调用重试）
            logger.warning("决策存量迁移失败（不阻断）: %s", e)
        self._indices_ready = True

    async def get_decision(self, decision_id: str, workspace_id: str) -> Optional[DecisionRecord]:
        """按 ID 读取（隔离条件：decision_id AND workspace_id）。"""
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (n:Decision {uuid: $uuid, group_id: $ws}) RETURN n",
            uuid=decision_id,
            ws=workspace_id,
        )
        if not records:
            return None
        return DecisionRecord.from_node_properties(neo4j_driver.node_props(records[0]["n"]))

    async def save_decision_node(self, record: DecisionRecord, embedder: Any = None) -> str:
        await self.ensure_indices()
        driver = get_decision_driver()
        if not await self._save_via_graphiti(record, driver, embedder):
            await driver.execute_query(
                "MERGE (n:Decision:Entity {uuid: $uuid}) "
                "SET n.name = $name, n.group_id = $group_id, n.summary = $summary, "
                "n.created_at = $created_at",
                uuid=record.decision_id,
                name=record.recommended_option or record.decision_type,
                group_id=record.workspace_id,
                summary=(record.context_summary or "")[:2000],
                created_at=record.to_node_properties()["created_at"],
            )
        # SET 扩展属性（ADR-076：DecisionRecord 完整字段 + 显式 workspace_id 属性双轨）
        await driver.execute_query(
            "MATCH (n:Decision {uuid: $uuid, group_id: $group_id}) SET n += $extensions",
            uuid=record.decision_id,
            group_id=record.workspace_id,
            extensions=record.to_node_properties(),
        )
        return record.decision_id

    async def _save_via_graphiti(
        self, record: DecisionRecord, driver: Any, embedder: Any
    ) -> bool:
        """EntityNode 三步法落节点；不可用时返回 False 由调用方降级为纯 Cypher。"""
        if not neo4j_driver.GRAPHITI_AVAILABLE or embedder is None:
            return False
        node = neo4j_driver.EntityNode(
            name=f"{record.recommended_option or record.decision_type}",
            labels=["Decision"],
            group_id=record.workspace_id,
            summary=record.context_summary[:2000] if record.context_summary else "",
        )
        node.uuid = record.decision_id  # 以生成的 decision_id 作为节点 uuid
        try:
            await node.generate_name_embedding(embedder)
        except Exception as emb_err:
            logger.warning("决策名 embedding 生成失败: %s", emb_err)
        if not node.name_embedding:
            # 审计关键路径零 LLM 原则：embedding 不可用不阻断决策落库。
            # EntityNode.save 内部会对空向量调用 setNodeVectorProperty 抛错，
            # 故降级为纯 Cypher 创建（先例检索自动走文本扫描降级路径）
            logger.warning("embedding 为空，降级为纯 Cypher 创建决策节点")
            return False
        await node.save(driver)
        return True

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

    async def update_outcome(
        self,
        decision_id: str,
        workspace_id: str,
        patch: StatusOutcomePatch,
        feedback_summary: Optional[str] = None,
    ) -> bool:
        """状态与结果回填：一次 `SET n += $patch`（E34 原子写）。

        刻意不逐字段 SET：`status` 与 `outcome` 必须同一次写入，
        `updated_at` 也只有 patch 里那一份写法（详情页"状态同步中"计时依赖它）。
        更新条件含 decision_id AND workspace_id（隔离双保险）。
        """
        driver = get_decision_driver()
        records, _, _ = await driver.execute_query(
            "MATCH (n:Decision {uuid: $did, group_id: $ws}) "
            "SET n += $patch, n.feedback_summary = $summary "
            "RETURN n.uuid AS uuid",
            did=decision_id,
            ws=workspace_id,
            patch=patch.to_node_patch(),
            summary=feedback_summary,
        )
        return bool(records)

    def edge_type_values(self) -> List[str]:
        return [t.value for t in CausalLinkType]
