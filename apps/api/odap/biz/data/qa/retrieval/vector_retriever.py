"""Vector 语义相似度检索支柱 - 复用 Graphiti search_hybrid"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import RetrievalResult, RetrievalPillar

logger = logging.getLogger(__name__)


class QueryRewriter:
    """查询改写器: HyDE + Multi-Query"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def hyde_rewrite(self, query: str) -> str:
        """HyDE: 生成假设性回答用于检索。LLM 不可用时返回原查询。"""
        if not self.llm_client:
            return query
        try:
            prompt = (
                f"请针对以下问题，写一段详细的回答（不需要完全正确，用于语义检索）：\n"
                f"问题：{query}\n回答："
            )
            result = self.llm_client.generate(prompt, max_tokens=256, timeout=5)
            if result and len(result.strip()) > 20:
                return result.strip()
        except Exception as e:
            logger.debug(f"HyDE rewrite failed: {e}")
        return query

    def multi_query(self, query: str) -> List[str]:
        """Multi-Query: 将原查询分解为多个子查询。LLM 不可用时返回原查询。"""
        if not self.llm_client:
            return [query]
        try:
            prompt = (
                f"请将以下问题改写为3个不同角度的搜索查询（每行一个，不要编号）：\n"
                f"原问题：{query}"
            )
            result = self.llm_client.generate(prompt, max_tokens=256, timeout=5)
            if result:
                lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
                if len(lines) >= 2:
                    return [query] + lines[:3]  # 保留原查询 + 最多3个改写
        except Exception as e:
            logger.debug(f"Multi-query rewrite failed: {e}")
        return [query]


class VectorRetriever:
    """Vector 语义检索器: 封装 Graphiti search_hybrid"""

    def __init__(self, graph_manager=None, query_rewriter: Optional[QueryRewriter] = None):
        self.graph_manager = graph_manager
        self.query_rewriter = query_rewriter or QueryRewriter()

    def search(self, query: str, top_k: int = 10,
               workspace_id: str = "",
               scenario_id: Optional[str] = None,
               rewrite: bool = True) -> List[RetrievalResult]:
        """语义检索: Graphiti search_hybrid 优先, GraphManager.search 降级"""
        queries = [query]
        if rewrite:
            queries = self.query_rewriter.multi_query(query)

        all_results: List[RetrievalResult] = []
        for q in queries:
            results = self._search_single(q, top_k, workspace_id, scenario_id)
            all_results.extend(results)

        # 去重 (by doc_id) + 合并分数
        seen: Dict[str, RetrievalResult] = {}
        for r in all_results:
            if r.doc_id in seen:
                seen[r.doc_id].score = max(seen[r.doc_id].score, r.score)
            else:
                seen[r.doc_id] = r

        # 排序
        sorted_results = sorted(seen.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:top_k]

    def _search_single(self, query: str, top_k: int,
                       workspace_id: str, scenario_id: Optional[str]) -> List[RetrievalResult]:
        """单次检索"""
        if not self.graph_manager:
            return []

        # 主路径: search_hybrid
        try:
            if hasattr(self.graph_manager, 'search_hybrid'):
                raw_results = self.graph_manager.search_hybrid(query, top_k=top_k)
                return self._convert_results(raw_results, "graphiti")
        except Exception as e:
            logger.debug(f"search_hybrid failed: {e}")

        # 降级路径: search
        try:
            if hasattr(self.graph_manager, 'search'):
                raw_results = self.graph_manager.search(query, limit=top_k)
                return self._convert_results(raw_results, "graph_search")
        except Exception as e:
            logger.debug(f"search failed: {e}")

        return []

    def _convert_results(self, raw_results: Any, source: str) -> List[RetrievalResult]:
        """将 Graphiti/GraphManager 结果转为统一 RetrievalResult"""
        results: List[RetrievalResult] = []
        if not raw_results:
            return results

        items = raw_results if isinstance(raw_results, list) else [raw_results]
        for item in items:
            if isinstance(item, dict):
                results.append(RetrievalResult(
                    doc_id=item.get("entity_id", item.get("uuid", "")),
                    content=item.get("name", item.get("fact", item.get("content", ""))),
                    score=float(item.get("score", item.get("similarity", 0.0))),
                    pillar=RetrievalPillar.VECTOR,
                    source=source,
                    metadata=item,
                    entities=item.get("entities", []),
                ))
            elif hasattr(item, '__dict__'):
                d = item.__dict__
                results.append(RetrievalResult(
                    doc_id=str(getattr(item, 'entity_id', getattr(item, 'uuid', ''))),
                    content=str(getattr(item, 'name', getattr(item, 'fact', ''))),
                    score=float(getattr(item, 'score', getattr(item, 'similarity', 0.0))),
                    pillar=RetrievalPillar.VECTOR,
                    source=source,
                    metadata=d,
                ))
        return results
