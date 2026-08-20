"""决策智能服务编排层（ADR-076 §4）

职责：路由 ↔ 存储 桥梁，集成 Graphiti 协作面（审计 Episode / 向量检索 / embedder）
与 OPA 前置门禁。所有公开方法强制 workspace 隔离。
"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.decision.decision_record.impl import Neo4jDecisionStore
from odap.biz.decision.decision_record.interfaces import IDecisionStore
from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionCausalLink,
    DecisionChain,
    DecisionGateResult,
    DecisionImpact,
    DecisionOutcome,
    DecisionRecord,
)

logger = logging.getLogger(__name__)

_service: Optional["DecisionService"] = None


def _graph_manager():
    """延迟获取 GraphManager 单例（未连接时返回降级行为由调用方处理）。"""
    from odap.infra.graph.graph_service import GraphManager

    return GraphManager()


class DecisionService:
    """决策智能服务（record / chain / similar / impact / outcome / causal-link / check-rules）。"""

    def __init__(self, store: Optional[IDecisionStore] = None) -> None:
        self.store: IDecisionStore = store or Neo4jDecisionStore()

    # ---------------- 4.1 record ----------------

    async def record_decision(self, record: DecisionRecord) -> DecisionRecord:
        """决策持久化为一等公民节点 + 证据/因果边 + Graphiti 审计 Episode。"""
        if not record.workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")

        gm = _graph_manager()
        embedder = getattr(getattr(gm, "graph", None), "embedder", None)
        record.decision_id = await self.store.save_decision_node(record, embedder=embedder)

        # 证据边（DERIVED_FROM）
        if record.evidence_entity_ids or record.evidence_episode_ids:
            try:
                await self.store.create_derived_from_edges(
                    record.decision_id,
                    record.workspace_id,
                    record.evidence_entity_ids,
                    record.evidence_episode_ids,
                )
            except Exception as e:
                logger.warning("DERIVED_FROM 证据边建立失败（不阻断）: %s", e)

        # 父决策因果边（CAUSED_BY）
        if record.parent_decision_id:
            try:
                await self.add_causal_relationship(
                    record.decision_id,
                    record.parent_decision_id,
                    CausalLinkType.CAUSED_BY,
                    record.workspace_id,
                )
            except Exception as e:
                logger.warning("CAUSED_BY 边建立失败（不阻断）: %s", e)

        # 先例引用留痕（PRECEDENT_FOR：先例 → 新决策）
        for precedent_id in record.precedent_decision_ids:
            try:
                await self.add_causal_relationship(
                    precedent_id,
                    record.decision_id,
                    CausalLinkType.PRECEDENT_FOR,
                    record.workspace_id,
                )
            except Exception as e:
                logger.warning("PRECEDENT_FOR 留痕失败（不阻断）: %s", e)

        # Graphiti 审计 Episode（决策即审计事件，零 LLM）
        try:
            await gm.save_audit_episode(
                {
                    "event_type": "decision_recorded",
                    "decision_id": record.decision_id,
                    "workspace_id": record.workspace_id,
                    "decision_type": record.decision_type,
                    "decision_method": record.decision_method,
                    "recommended_option": record.recommended_option,
                    "confidence": record.confidence,
                    "agent_id": record.agent_id,
                    "opa_approved": record.opa_approved,
                    "evidence_entity_count": len(record.evidence_entity_ids),
                    "evidence_episode_count": len(record.evidence_episode_ids),
                },
                valid_at=record.valid_at,
                source_description="decision_record",
            )
        except Exception as e:
            logger.warning("决策审计 Episode 写入失败（不阻断）: %s", e)

        return record

    # ---------------- 4.2 trace chain ----------------

    async def trace_decision_chain(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionChain]:
        return await self.store.trace_chain(decision_id, workspace_id, max_hops)

    # ---------------- 4.3 find similar ----------------

    async def find_similar_decisions(
        self, workspace_id: str, query: str, top_k: int = 5
    ) -> List[DecisionRecord]:
        """先例搜索：Graphiti search_ 向量检索优先，Cypher 文本扫描降级。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")

        # 主路径：Graphiti search_（0.29.2 已核验签名，天然 group_ids 过滤）
        try:
            from graphiti_core.search.search_filters import SearchFilters

            gm = _graph_manager()
            client = getattr(gm, "graph", None)
            if client is not None and hasattr(client, "search_"):
                results = await client.search_(
                    query=query,
                    group_ids=[workspace_id],
                    search_filter=SearchFilters(node_labels=["Decision"]),
                )
                nodes = getattr(results, "nodes", []) or []
                decisions: List[DecisionRecord] = []
                for node in nodes[:top_k]:
                    uuid = getattr(node, "uuid", None)
                    if not uuid:
                        continue
                    rec = await self.store.get_decision(uuid, workspace_id)
                    if rec is not None:
                        decisions.append(rec)
                if decisions:
                    return decisions
        except Exception as e:
            logger.warning("Graphiti 向量先例检索失败，降级 Cypher 文本扫描: %s", e)

        # 降级路径
        return await self.store.find_similar_by_text(workspace_id, query, top_k)

    # ---------------- 4.4 analyze impact ----------------

    async def analyze_decision_impact(
        self, decision_id: str, workspace_id: str, max_hops: int = 3
    ) -> Optional[DecisionImpact]:
        return await self.store.analyze_impact(decision_id, workspace_id, max_hops)

    # ---------------- 4.5 causal relationship ----------------

    async def add_causal_relationship(
        self,
        from_decision_id: str,
        to_decision_id: str,
        link_type: CausalLinkType,
        workspace_id: str,
    ) -> DecisionCausalLink:
        """建立因果边：同空间校验 + CAUSED_BY 环检测。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")

        # 两端存在性 + 同空间校验
        from_rec = await self.store.get_decision(from_decision_id, workspace_id)
        to_rec = await self.store.get_decision(to_decision_id, workspace_id)
        if from_rec is None or to_rec is None:
            raise ValueError("因果边两端决策必须存在且属于同一工作空间")

        # CAUSED_BY 环检测（新边 from->to 成环条件：to 已可达 from）
        if link_type == CausalLinkType.CAUSED_BY:
            has_path = await self.store.has_caused_by_path(
                to_decision_id, from_decision_id, workspace_id
            )
            if has_path:
                raise ValueError(
                    f"禁止成环：{to_decision_id} 已可达 {from_decision_id}（CAUSED_BY 链）"
                )

        link = DecisionCausalLink(
            from_decision_id=from_decision_id,
            to_decision_id=to_decision_id,
            link_type=link_type,
            workspace_id=workspace_id,
        )
        await self.store.add_causal_link(link)
        return link

    # ---------------- 4.6 check rules（落库前门禁） ----------------

    async def check_decision_rules(
        self,
        workspace_id: str,
        user: Dict[str, Any],
        action: str,
        resource: Dict[str, Any],
        environment: Optional[Dict[str, Any]] = None,
    ) -> DecisionGateResult:
        """落库前规则门禁。Phase 1 = OPA 权限门禁前移；ADR-075 落地后接入业务规则第二道门禁。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
        env = dict(environment or {})
        env["workspace_id"] = workspace_id

        from odap.infra.opa.opa_service import OPAManagerV2

        opa_result = await OPAManagerV2().check_permission_abac(
            user=user,
            action=action,
            resource=resource,
            environment=env,
        )
        return DecisionGateResult(
            approved=bool(opa_result.get("allow")),
            gate="opa",
            details=opa_result,
        )

    # ---------------- 4.7 outcome backfill ----------------

    async def update_decision_outcome(
        self,
        decision_id: str,
        workspace_id: str,
        outcome: DecisionOutcome,
        outcome_details: Dict[str, Any],
        feedback_summary: Optional[str] = None,
    ) -> bool:
        return await self.store.update_outcome(
            decision_id, workspace_id, outcome, outcome_details, feedback_summary
        )

    # ---------------- TRIGGERED 边（pipeline 集成） ----------------

    async def link_triggered_action(
        self, decision_id: str, workspace_id: str, action_record: Dict[str, Any]
    ) -> None:
        """Decision -[:TRIGGERED]-> ActionRecord（ADR-076 Q3 决议）。"""
        await self.store.create_triggered_edge(decision_id, workspace_id, action_record)


def get_decision_service() -> DecisionService:
    """决策服务单例（与 get_action_executor 等仓库惯例一致的同步单例）。"""
    global _service
    if _service is None:
        _service = DecisionService()
    return _service
