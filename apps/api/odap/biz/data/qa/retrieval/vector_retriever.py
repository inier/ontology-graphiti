"""Vector 语义相似度检索支柱 - 复用 Graphiti search_hybrid"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import RetrievalResult, RetrievalPillar

logger = logging.getLogger(__name__)


class QueryRewriter:
    """查询改写器: 基于 USL 术语字典的**确定性改写**（同义词 → canonical）。

    本体论原则（严格）：
    - 禁用 HyDE（生成假设回答）与 LLM Multi-Query（生成改写）—— 两者都引入幻觉。
    - 改写只做一件事：把查询中命中的 USL 同义词替换为 canonical（精确字典查表）。
    - 未命中 USL 的词保持原样（不猜测、不生成）。
    """

    def __init__(self, llm_client=None, term_resolver=None):
        # llm_client 保留以兼容旧调用方，但**不再使用**（确定性改写无 LLM）。
        self.llm_client = None
        if term_resolver is None:
            from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
                UslTermResolver,
            )
            term_resolver = UslTermResolver()
        self.term_resolver = term_resolver

    def load_usl_terms(self, domain_id: str, terms: List[Dict[str, Any]]) -> None:
        """加载领域 USL 术语，供确定性改写"""
        self.term_resolver.load_terms(domain_id, terms)

    def hyde_rewrite(self, query: str) -> str:
        """确定性改写：同义词 → canonical（等价于 rewrite，保留接口兼容）"""
        return self.rewrite(query)

    def rewrite(self, query: str, domain_id: str = "") -> str:
        """确定性改写：将查询中命中的同义词替换为 canonical。

        实现：对查询分词（中文按字符滑动匹配已知术语），
        命中 USL 的同义词/别名替换为 canonical；未命中保持原样。
        """
        if not query:
            return query
        # 已知术语（canonical 之外的表达）按长度降序，优先匹配长词
        known = self.term_resolver._maps.get(domain_id, {}) if domain_id else {}
        if not known and not domain_id:
            # 合并全部已加载领域
            for m in self.term_resolver._maps.values():
                known.update(m)
        # 只替换"非 canonical 本身"的表达（canonical 无需替换）
        replacements = [
            (expr, canonical)
            for expr, canonical in known.items()
            if expr != canonical
        ]
        # 按表达长度降序，长词优先（避免子串误替换）
        replacements.sort(key=lambda kv: len(kv[0]), reverse=True)

        result = query
        for expr, canonical in replacements:
            if expr in result:
                result = result.replace(expr, canonical)
        return result

    def multi_query(self, query: str) -> List[str]:
        """确定性多查询：仅返回 [原查询, canonical 改写]，不生成新查询。

        若改写后与原查询相同（无同义词命中），返回单元素 [query]。
        """
        rewritten = self.rewrite(query)
        if rewritten and rewritten != query:
            return [query, rewritten]
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
