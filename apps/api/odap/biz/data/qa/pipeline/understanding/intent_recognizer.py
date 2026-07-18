"""Stage 1: 查询理解 - 意图识别 + 实体提取 + 查询改写"""

import logging
import re
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import QueryIntent, QueryUnderstanding

logger = logging.getLogger(__name__)

# ── 意图规则 ──────────────────────────────────────────────────────────

_INTENT_RULES: List[tuple] = [
    # (意图, 正则, 权重)
    (QueryIntent.KEYWORD_LOOKUP, re.compile(r'查找|搜索|找到|有没有|是否包含|精确匹配|叫什么'), 0.8),
    (QueryIntent.SEMANTIC_SEARCH, re.compile(r'什么是|解释|说明|描述|介绍|含义|概念|类似|像'), 0.7),
    (QueryIntent.GRAPH_TRAVERSE, re.compile(r'关联|关系|连接|路径|邻居|相连|从.*到|跳|层级'), 0.85),
    (QueryIntent.COMPLEX_ANALYSIS, re.compile(r'分析|对比|比较|趋势|统计|排名|分布|综合|评估'), 0.8),
    (QueryIntent.TEMPORAL_QUERY, re.compile(r'什么时候|何时|时间|历史|变化|之前|之后|最近|上周|本月|去年'), 0.85),
    (QueryIntent.ACTION, re.compile(r'执行|运行|启动|创建|删除|更新|触发|部署|调用'), 0.9),
]

# 代词列表（用于共指消解和澄清检测）
_PRONOUNS_ZH = re.compile(r'(它|他|她|这个|那个|这些|那些|其|此|该)')


class IntentRecognizer:
    """意图识别器: 规则优先 + LLM 增强"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def recognize(self, query: str) -> tuple:
        """返回 (QueryIntent, confidence)"""
        # 规则匹配
        best_intent = QueryIntent.SEMANTIC_SEARCH
        best_score = 0.0

        for intent, pattern, weight in _INTENT_RULES:
            if pattern.search(query):
                if weight > best_score:
                    best_score = weight
                    best_intent = intent

        # 多意图冲突时，尝试 LLM 分类
        matched_count = sum(1 for _, pattern, _ in _INTENT_RULES if pattern.search(query))
        if matched_count >= 2 and self.llm_client:
            llm_intent = self._llm_classify(query)
            if llm_intent:
                best_intent = llm_intent
                best_score = 0.9

        return best_intent, best_score

    def _llm_classify(self, query: str) -> Optional[QueryIntent]:
        """LLM 意图分类（可选增强）"""
        if not self.llm_client:
            return None
        try:
            intent_names = ", ".join(i.value for i in QueryIntent)
            prompt = (
                f"请将以下中文查询分类为以下意图之一: [{intent_names}]\n"
                f"仅输出意图名称，不要解释。\n查询: {query}"
            )
            result = self.llm_client.generate(prompt, max_tokens=32, timeout=5)
            if result:
                result = result.strip().lower()
                for intent in QueryIntent:
                    if intent.value in result:
                        return intent
        except Exception as e:
            logger.debug(f"LLM intent classify failed: {e}")
        return None


class EntityExtractor:
    """实体提取器: 从自然语言中提取查询实体"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def extract(self, query: str) -> List[str]:
        """提取查询中的实体名"""
        entities: List[str] = []

        # 规则提取: 引号内的内容
        quoted = re.findall(r'[""「」『』](.+?)[""「」『』]', query)
        entities.extend(quoted)

        # 规则提取: "的" 前面的名词短语
        de_pattern = re.findall(r'([\u4e00-\u9fff]{2,6})的', query)
        entities.extend(de_pattern)

        # 规则提取: 大写英文实体
        en_entities = re.findall(r'\b[A-Z][a-zA-Z]+\b', query)
        entities.extend(en_entities)

        # LLM 增强（可选）
        if len(entities) < 2 and self.llm_client:
            llm_entities = self._llm_extract(query)
            if llm_entities:
                entities.extend(llm_entities)

        # 去重 + 过滤
        seen = set()
        result = []
        for e in entities:
            e = e.strip()
            if e and e not in seen and len(e) >= 2:
                seen.add(e)
                result.append(e)

        return result

    def _llm_extract(self, query: str) -> Optional[List[str]]:
        """LLM 实体提取"""
        if not self.llm_client:
            return None
        try:
            prompt = (
                f"从以下查询中提取实体名称，每行一个，不要编号，不要解释：\n{query}"
            )
            result = self.llm_client.generate(prompt, max_tokens=128, timeout=5)
            if result:
                lines = [l.strip().lstrip("-• ") for l in result.strip().split("\n") if l.strip()]
                return [l for l in lines if len(l) >= 2][:5]
        except Exception as e:
            logger.debug(f"LLM entity extract failed: {e}")
        return None

    def resolve_coreferences(self, query: str, context_entities: List[str]) -> str:
        """共指消解: 替换代词为上下文实体"""
        if not context_entities:
            return query

        resolved = query
        for pronoun in ["它", "他", "她", "这个", "那个", "其", "此", "该"]:
            if pronoun in resolved and context_entities:
                # 用最近的实体替换第一个匹配的代词
                resolved = resolved.replace(pronoun, context_entities[-1], 1)
                break

        return resolved


class UnderstandingStage:
    """Stage 1: 查询理解"""

    def __init__(self, llm_client=None):
        self.intent_recognizer = IntentRecognizer(llm_client)
        self.entity_extractor = EntityExtractor(llm_client)

    def analyze(self, query: str, context: Optional[Dict[str, Any]] = None) -> QueryUnderstanding:
        """分析查询: 意图识别 + 实体提取 + 澄清检测"""
        context = context or {}

        # 共指消解
        context_entities = context.get("entities", [])
        resolved_query = self.entity_extractor.resolve_coreferences(query, context_entities)

        # 意图识别
        intent, confidence = self.intent_recognizer.recognize(resolved_query)

        # 实体提取
        entities = self.entity_extractor.extract(resolved_query)

        # 澄清检测
        needs_clarification, clarification_reason = self._check_clarification(
            resolved_query, entities, confidence
        )

        return QueryUnderstanding(
            original_query=query,
            intent=intent,
            extracted_entities=entities,
            rewritten_queries=[resolved_query] if resolved_query != query else [],
            confidence=confidence,
            needs_clarification=needs_clarification,
            clarification_reason=clarification_reason,
        )

    def _check_clarification(self, query: str, entities: List[str],
                             confidence: float) -> tuple:
        """检测是否需要澄清"""
        # 模糊代词
        if _PRONOUNS_ZH.search(query) and not entities:
            return True, "ambiguous_pronoun"

        # 问题过短
        effective_chars = len(re.sub(r'\s+', '', query))
        if effective_chars < 4:
            return True, "too_short"

        # 置信度过低
        if confidence < 0.3:
            return True, "low_confidence"

        return False, None
