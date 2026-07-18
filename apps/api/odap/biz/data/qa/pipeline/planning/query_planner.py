"""Stage 2: 查询规划 - 选择检索支柱 + 生成查询计划"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import (
    FusionStrategy, QueryIntent, QueryPlan, QueryUnderstanding,
    RetrievalPillar, SubQuery
)

logger = logging.getLogger(__name__)


# ── 意图→支柱映射 ─────────────────────────────────────────────────────

_INTENT_PILLAR_MAP = {
    QueryIntent.KEYWORD_LOOKUP: [RetrievalPillar.BM25],
    QueryIntent.SEMANTIC_SEARCH: [RetrievalPillar.VECTOR],
    QueryIntent.GRAPH_TRAVERSE: [RetrievalPillar.GRAPH],
    QueryIntent.COMPLEX_ANALYSIS: [RetrievalPillar.BM25, RetrievalPillar.VECTOR, RetrievalPillar.GRAPH],
    QueryIntent.TEMPORAL_QUERY: [RetrievalPillar.GRAPH],
    QueryIntent.ACTION: [],
}

_INTENT_FUSION_MAP = {
    QueryIntent.KEYWORD_LOOKUP: FusionStrategy.WEIGHTED,
    QueryIntent.SEMANTIC_SEARCH: FusionStrategy.WEIGHTED,
    QueryIntent.GRAPH_TRAVERSE: FusionStrategy.CASCADE,
    QueryIntent.COMPLEX_ANALYSIS: FusionStrategy.RRF,
    QueryIntent.TEMPORAL_QUERY: FusionStrategy.CASCADE,
    QueryIntent.ACTION: FusionStrategy.WEIGHTED,
}


class QueryPlanner:
    """查询规划器: 根据理解结果生成查询计划"""

    def create_plan(self, understanding: QueryUnderstanding,
                    constraints: Optional[Dict[str, Any]] = None) -> QueryPlan:
        """生成查询计划"""
        constraints = constraints or {}
        top_k = constraints.get("top_k", 10)
        mode = constraints.get("mode", "auto")

        # 确定支柱
        pillars = self._select_pillars(understanding.intent, mode)

        # 生成子查询
        sub_queries = self._generate_sub_queries(understanding, pillars, top_k)

        # 确定融合策略
        fusion_strategy = _INTENT_FUSION_MAP.get(understanding.intent, FusionStrategy.WEIGHTED)

        return QueryPlan(
            pillars=[p.value for p in pillars],
            sub_queries=sub_queries,
            fusion_strategy=fusion_strategy,
            top_k=top_k,
        )

    def _select_pillars(self, intent: QueryIntent, mode: str) -> List[RetrievalPillar]:
        """选择检索支柱"""
        # 手动模式强制指定
        if mode == "keyword":
            return [RetrievalPillar.BM25]
        elif mode == "semantic":
            return [RetrievalPillar.VECTOR]
        elif mode == "graph":
            return [RetrievalPillar.GRAPH]

        # 自动模式: 根据意图
        pillars = _INTENT_PILLAR_MAP.get(intent, [RetrievalPillar.VECTOR, RetrievalPillar.BM25])
        return list(pillars)  # 返回副本

    def _generate_sub_queries(self, understanding: QueryUnderstanding,
                              pillars: List[RetrievalPillar],
                              top_k: int) -> List[SubQuery]:
        """为每个支柱生成子查询"""
        sub_queries: List[SubQuery] = []
        query = understanding.rewritten_queries[0] if understanding.rewritten_queries else understanding.original_query

        for pillar in pillars:
            if pillar == RetrievalPillar.BM25:
                sub_queries.append(SubQuery(
                    pillar=pillar.value,
                    query=query,
                    params={"top_k": top_k},
                ))
            elif pillar == RetrievalPillar.VECTOR:
                # Vector 支柱可能使用改写后的查询
                vector_query = query
                if understanding.rewritten_queries:
                    vector_query = understanding.rewritten_queries[0]
                sub_queries.append(SubQuery(
                    pillar=pillar.value,
                    query=vector_query,
                    params={"top_k": top_k, "rewrite": True},
                ))
            elif pillar == RetrievalPillar.GRAPH:
                # Graph 支柱: 确定模式
                graph_mode = self._determine_graph_mode(understanding)
                sub_queries.append(SubQuery(
                    pillar=pillar.value,
                    query=query,
                    params={"top_k": top_k},
                    mode=graph_mode,
                ))

        return sub_queries

    def _determine_graph_mode(self, understanding: QueryUnderstanding) -> str:
        """确定 Graph 查询模式"""
        if understanding.intent == QueryIntent.TEMPORAL_QUERY:
            return "temporal"
        if understanding.intent == QueryIntent.COMPLEX_ANALYSIS:
            return "cypher"
        if understanding.intent == QueryIntent.GRAPH_TRAVERSE:
            return "auto"
        return "neighbors"


class PlanningStage:
    """Stage 2: 查询规划"""

    def __init__(self):
        self.planner = QueryPlanner()

    def create_plan(self, understanding: QueryUnderstanding,
                    constraints: Optional[Dict[str, Any]] = None) -> QueryPlan:
        """创建查询计划"""
        return self.planner.create_plan(understanding, constraints)
