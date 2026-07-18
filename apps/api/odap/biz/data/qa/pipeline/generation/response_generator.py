"""Stage 5: 回答生成 - LLM 生成 + 溯源追踪"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import (
    QueryResponse, QueryUnderstanding, RetrievalResultSet, SourceReference
)

logger = logging.getLogger(__name__)


class SourceTracer:
    """溯源追踪器"""

    def trace(self, result_set: RetrievalResultSet) -> List[SourceReference]:
        """从检索结果提取来源引用"""
        sources: List[SourceReference] = []
        seen = set()

        for r in result_set.results:
            if r.doc_id in seen:
                continue
            seen.add(r.doc_id)
            sources.append(SourceReference(
                doc_id=r.doc_id,
                content=r.content[:200] if r.content else "",
                score=r.score,
                pillar=r.pillar,
                source=r.source,
                entity_id=r.metadata.get("entity_id"),
            ))

        return sources


class ResponseGenerator:
    """LLM 回答生成器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate(self, query: str, result_set: RetrievalResultSet,
                 understanding: QueryUnderstanding,
                 stream: bool = False) -> str:
        """生成回答。LLM 不可用时使用模板回答。"""
        if not result_set.results:
            return self._no_result_template(query, understanding)

        # 构建上下文
        context = self._build_context(result_set)

        if self.llm_client:
            try:
                prompt = (
                    f"基于以下检索结果回答用户问题。请引用来源，如果检索结果不足以回答，请说明。\n\n"
                    f"检索结果:\n{context}\n\n"
                    f"用户问题: {query}\n回答:"
                )
                result = self.llm_client.generate(prompt, max_tokens=1024, timeout=15)
                if result and len(result.strip()) > 10:
                    return result.strip()
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")

        # 降级: 模板回答
        return self._template_answer(query, result_set, understanding)

    def _build_context(self, result_set: RetrievalResultSet, max_items: int = 5) -> str:
        """构建 LLM 上下文"""
        parts = []
        for i, r in enumerate(result_set.results[:max_items], 1):
            source_tag = f"[{r.pillar}:{r.source}]"
            parts.append(f"{i}. {source_tag} {r.content[:300]}")
        return "\n".join(parts)

    def _no_result_template(self, query: str, understanding: QueryUnderstanding) -> str:
        """无结果模板"""
        if understanding.needs_clarification:
            reason_map = {
                "ambiguous_pronoun": "问题中包含模糊代词，请明确指代对象",
                "too_short": "问题描述过于简短，请提供更多细节",
                "low_confidence": "无法确定查询意图，请更详细地描述您的问题",
            }
            reason = reason_map.get(understanding.clarification_reason or "", "请提供更多信息")
            return f"抱歉，{reason}。您可以尝试：\n1. 使用更具体的实体名称\n2. 说明查询的关联方向\n3. 提供更多上下文信息"
        return "未检索到相关信息。请尝试调整查询条件或使用不同的关键词。"

    def _template_answer(self, query: str, result_set: RetrievalResultSet,
                         understanding: QueryUnderstanding) -> str:
        """模板回答（LLM 不可用时降级）"""
        top_results = result_set.results[:5]
        if not top_results:
            return self._no_result_template(query, understanding)

        parts = [f"关于「{query}」，检索到以下相关信息：\n"]
        for i, r in enumerate(top_results, 1):
            pillar_tag = {"bm25": "关键词匹配", "vector": "语义检索", "graph": "图关联"}.get(r.pillar, r.pillar)
            parts.append(f"{i}. [{pillar_tag}] {r.content[:200]}")

        parts.append(f"\n（共检索到 {len(result_set.results)} 条相关结果）")
        return "\n".join(parts)


class GenerationStage:
    """Stage 5: 回答生成"""

    def __init__(self, llm_client=None):
        self.generator = ResponseGenerator(llm_client)
        self.tracer = SourceTracer()

    async def generate(self, result_set: RetrievalResultSet,
                       understanding: QueryUnderstanding,
                       query: str, stream: bool = False) -> QueryResponse:
        """生成最终回答"""
        answer = self.generator.generate(query, result_set, understanding, stream)
        sources = self.tracer.trace(result_set)

        # 计算支柱贡献度
        pillar_contributions: Dict[str, float] = {}
        total = len(result_set.results) or 1
        for r in result_set.results:
            pillar_contributions[r.pillar] = pillar_contributions.get(r.pillar, 0) + 1
        for k in pillar_contributions:
            pillar_contributions[k] = round(pillar_contributions[k] / total, 2)

        return QueryResponse(
            answer=answer,
            sources=sources,
            understanding=understanding,
            pillar_contributions=pillar_contributions,
            metadata={
                "result_count": len(result_set.results),
                "source_count": len(sources),
            },
        )
