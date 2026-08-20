"""Stage 4: 结果融合 - 多源结果融合 + 重排序"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import (
    FusionStrategy, QueryUnderstanding, RetrievalResult, RetrievalResultSet
)

logger = logging.getLogger(__name__)


class Reranker:
    """重排序器（**确定性排序**，无 LLM，无魔法权重）。

    本体论原则（严格）：
    - 排序由固定优先级决定，不依赖向量相似度分数（score 仅作展示字段）。
    - 支柱优先级（本体结构遍历最可信）: graph > vector > bm25。
    - 同支柱内按 doc_id 稳定排序（确定性，跨调用一致）。
    """

    # 支柱确定性优先级（高 → 低）
    PILLAR_PRIORITY = {"graph": 0, "vector": 1, "bm25": 2}

    def __init__(self, llm_client=None):
        # llm_client 保留以兼容旧调用方，但**不再使用**（确定性排序无 LLM）。
        self.llm_client = None

    def rerank(self, query: str, results: List[RetrievalResult],
               top_k: int = 10) -> List[RetrievalResult]:
        """确定性重排序：按支柱优先级 + doc_id 稳定排序。

        score 字段保留原值（供展示），但**不参与排序决定**。
        """
        if not results:
            return results

        results.sort(key=lambda r: (
            self.PILLAR_PRIORITY.get(r.pillar, 3),   # 支柱优先级（小在前）
            r.doc_id or "",                           # doc_id 稳定序（确定性）
        ))
        return results[:top_k]


class ResultFuser:
    """多源结果融合"""

    def merge_and_rerank(self, result_set: RetrievalResultSet,
                         query: str,
                         understanding: Optional[QueryUnderstanding] = None,
                         fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED,
                         top_k: int = 10) -> RetrievalResultSet:
        """融合多源结果 + 重排序"""
        results = result_set.results
        if not results:
            return result_set

        if fusion_strategy == FusionStrategy.RRF:
            results = self._rrf_fusion(results, top_k)
        elif fusion_strategy == FusionStrategy.CASCADE:
            results = self._cascade_fusion(results, top_k)
        else:
            results = self._weighted_fusion(results, top_k)

        result_set.results = results
        return result_set

    def _weighted_fusion(self, results: List[RetrievalResult],
                         top_k: int) -> List[RetrievalResult]:
        """加权融合: 去重 + 分数加权合并"""
        merged: Dict[str, RetrievalResult] = {}
        pillar_weights = {"bm25": 0.3, "vector": 0.5, "graph": 0.4}

        for r in results:
            weight = pillar_weights.get(r.pillar, 0.3)
            weighted_score = r.score * weight

            if r.doc_id in merged:
                # 合并分数: 取最大加权分
                existing = merged[r.doc_id]
                existing.score = max(existing.score, weighted_score)
                # 保留最高权重的支柱标记
                if weight > pillar_weights.get(existing.pillar, 0.3):
                    existing.pillar = r.pillar
            else:
                r.score = weighted_score
                merged[r.doc_id] = r

        sorted_results = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:top_k]

    def _rrf_fusion(self, results: List[RetrievalResult],
                     top_k: int, k: int = 60) -> List[RetrievalResult]:
        """Reciprocal Rank Fusion"""
        # 按支柱分组排序
        pillar_results: Dict[str, List[RetrievalResult]] = {}
        for r in results:
            pillar_results.setdefault(r.pillar, []).append(r)

        # 每个支柱内按分数排序
        for pillar, items in pillar_results.items():
            items.sort(key=lambda x: x.score, reverse=True)

        # RRF 打分
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, RetrievalResult] = {}

        for pillar, items in pillar_results.items():
            for rank, item in enumerate(items, 1):
                rrf_score = 1.0 / (k + rank)
                if item.doc_id in rrf_scores:
                    rrf_scores[item.doc_id] += rrf_score
                else:
                    rrf_scores[item.doc_id] = rrf_score
                    doc_map[item.doc_id] = item

        # 更新分数
        for doc_id, score in rrf_scores.items():
            doc_map[doc_id].score = score

        sorted_results = sorted(doc_map.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:top_k]

    def _cascade_fusion(self, results: List[RetrievalResult],
                        top_k: int) -> List[RetrievalResult]:
        """级联融合: BM25 优先, 不够再 Vector, 再 Graph"""
        pillar_order = ["bm25", "vector", "graph"]
        merged: Dict[str, RetrievalResult] = {}

        for pillar in pillar_order:
            pillar_items = [r for r in results if r.pillar == pillar]
            pillar_items.sort(key=lambda x: x.score, reverse=True)
            for r in pillar_items:
                if r.doc_id not in merged:
                    merged[r.doc_id] = r
                if len(merged) >= top_k:
                    break
            if len(merged) >= top_k:
                break

        return list(merged.values())[:top_k]


class FusionStage:
    """Stage 4: 结果融合"""

    def __init__(self, reranker: Optional[Reranker] = None):
        self.fuser = ResultFuser()
        self.reranker = reranker or Reranker()

    def merge_and_rerank(self, result_set: RetrievalResultSet,
                         query: str,
                         understanding: Optional[QueryUnderstanding] = None,
                         fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED,
                         top_k: int = 10) -> RetrievalResultSet:
        """融合 + 重排序"""
        # 融合
        fused = self.fuser.merge_and_rerank(
            result_set, query, understanding, fusion_strategy, top_k
        )
        # 重排序
        fused.results = self.reranker.rerank(query, fused.results, top_k)

        # 更新元数据
        fused.metadata["fusion_strategy"] = fusion_strategy.value
        fused.metadata["total_after_fusion"] = len(fused.results)

        return fused
