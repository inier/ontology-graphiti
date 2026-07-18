"""三支柱统一检索入口"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import (
    QueryPlan, RetrievalPillar, RetrievalResult, RetrievalResultSet, SubQuery
)
from odap.biz.data.qa.retrieval.bm25_retriever import BM25Retriever
from odap.biz.data.qa.retrieval.vector_retriever import VectorRetriever
from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever

logger = logging.getLogger(__name__)


class UnifiedRetriever:
    """三支柱统一检索 - 对外唯一入口"""

    def __init__(self, bm25_retriever: Optional[BM25Retriever] = None,
                 vector_retriever: Optional[VectorRetriever] = None,
                 graph_retriever: Optional[GraphRetriever] = None):
        self.bm25 = bm25_retriever or BM25Retriever()
        self.vector = vector_retriever or VectorRetriever()
        self.graph = graph_retriever or GraphRetriever()

    async def search(self, plan: QueryPlan,
                     workspace_id: str = "",
                     scenario_id: Optional[str] = None) -> RetrievalResultSet:
        """根据 QueryPlan 并行调度三支柱"""
        start_time = time.time()
        all_results: List[RetrievalResult] = []
        pillar_scores: Dict[str, float] = {}
        execution_times: Dict[str, float] = {}

        # 并行执行子查询
        tasks = []
        for sub_query in plan.sub_queries:
            tasks.append(self._execute_sub_query(
                sub_query, workspace_id, scenario_id
            ))

        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results_list):
                sub = plan.sub_queries[i]
                if isinstance(result, Exception):
                    logger.warning(f"Sub-query failed (pillar={sub.pillar}): {result}")
                    pillar_scores[sub.pillar] = 0.0
                    execution_times[sub.pillar] = 0.0
                    continue
                pillar_results, elapsed = result
                all_results.extend(pillar_results)
                pillar_scores[sub.pillar] = len(pillar_results)
                execution_times[sub.pillar] = elapsed

        total_time = (time.time() - start_time) * 1000

        return RetrievalResultSet(
            results=all_results,
            pillar_scores=pillar_scores,
            metadata={
                "execution_time_ms": execution_times,
                "total_time_ms": total_time,
                "plan_id": plan.plan_id,
            },
        )

    async def search_simple(self, query: str, top_k: int = 10,
                            workspace_id: str = "",
                            scenario_id: Optional[str] = None) -> RetrievalResultSet:
        """简单检索 - 自动选择所有可用支柱"""
        plan = QueryPlan(
            pillars=[p.value for p in RetrievalPillar],
            sub_queries=[
                SubQuery(pillar=RetrievalPillar.BM25.value, query=query, params={"top_k": top_k}),
                SubQuery(pillar=RetrievalPillar.VECTOR.value, query=query, params={"top_k": top_k}),
                SubQuery(pillar=RetrievalPillar.GRAPH.value, query=query, params={"top_k": top_k}, mode="auto"),
            ],
            top_k=top_k,
        )
        return await self.search(plan, workspace_id, scenario_id)

    async def _execute_sub_query(self, sub: SubQuery,
                                  workspace_id: str,
                                  scenario_id: Optional[str]) -> tuple:
        """执行单个子查询，返回 (results, elapsed_ms)"""
        start = time.time()
        results: List[RetrievalResult] = []
        top_k = sub.params.get("top_k", 10)

        try:
            if sub.pillar == RetrievalPillar.BM25:
                results = self.bm25.search(
                    query=sub.query, top_k=top_k,
                    workspace_id=workspace_id, scenario_id=scenario_id,
                    filters=sub.params.get("filters"),
                )
            elif sub.pillar == RetrievalPillar.VECTOR:
                results = self.vector.search(
                    query=sub.query, top_k=top_k,
                    workspace_id=workspace_id, scenario_id=scenario_id,
                    rewrite=sub.params.get("rewrite", True),
                )
            elif sub.pillar == RetrievalPillar.GRAPH:
                results = self.graph.search(
                    query=sub.query, top_k=top_k,
                    workspace_id=workspace_id, scenario_id=scenario_id,
                    mode=sub.mode or "auto",
                )
        except Exception as e:
            logger.error(f"Retrieval error (pillar={sub.pillar}): {e}")

        elapsed = (time.time() - start) * 1000
        return results, elapsed
