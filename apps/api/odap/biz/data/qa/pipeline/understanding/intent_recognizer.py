"""Stage 1: 查询理解 - 意图识别 + 实体提取 + 查询改写

本体论原则（严格）：
- 意图识别是**意图分发**：把自然语言映射到 QueryIntent 枚举（closed set）。
- 规则是**权威**（确定性），LLM 仅在规则无法区分（多规则同权重）时兜底。
- LLM 兜底结果必须**强校验**落在枚举内，否则丢弃（宁可 unknown 也不幻觉）。
"""

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
        """返回 (QueryIntent, confidence)。

        规则优先（确定性）；仅当多个规则**同权重平局**时才用 LLM 兜底，
        且兜底结果必须强校验落在 QueryIntent 枚举内，否则丢弃。
        """
        # 规则匹配：记录所有命中（意图, 权重）
        matches: List[tuple] = []
        for intent, pattern, weight in _INTENT_RULES:
            if pattern.search(query):
                matches.append((intent, weight))

        if not matches:
            # 无规则命中 → 默认语义搜索（确定性），不调用 LLM
            return QueryIntent.SEMANTIC_SEARCH, 0.3

        # 取最高权重
        max_weight = max(w for _, w in matches)
        top_matches = [(i, w) for i, w in matches if w == max_weight]

        if len(top_matches) == 1:
            # 唯一最高权重 → 直接确定（权威）
            return top_matches[0][0], top_matches[0][1]

        # 多意图同权重平局 → LLM 兜底（强校验）
        if self.llm_client:
            llm_intent = self._llm_classify(query)
            if llm_intent is not None:
                return llm_intent, 0.9

        # LLM 不可用或校验失败 → 取平局中首个（确定性稳定序）
        return top_matches[0][0], top_matches[0][1]

    def _llm_classify(self, query: str) -> Optional[QueryIntent]:
        """LLM 意图分类兜底（**强校验**：必须精确命中枚举值，否则丢弃）。

        返回值必须是 QueryIntent 枚举精确值（token 级精确匹配），
        不匹配则返回 None（由调用方回退确定性规则结果）。
        """
        if not self.llm_client:
            return None
        try:
            intent_names = ", ".join(i.value for i in QueryIntent)
            prompt = (
                f"请将以下中文查询分类为以下意图之一: [{intent_names}]\n"
                f"仅输出意图名称，不要解释。\n查询: {query}"
            )
            result = self.llm_client.generate(prompt, max_tokens=32, timeout=5)
            if not result:
                return None
            # 强校验：提取首个 token，与枚举值精确匹配（非子串匹配）
            raw = result.strip()
            for intent in QueryIntent:
                if raw == intent.value:
                    return intent
            # 容错：去掉首尾标点后精确匹配
            cleaned = raw.strip("。，,;； \n\t\"'")
            for intent in QueryIntent:
                if cleaned == intent.value:
                    return intent
            logger.debug("LLM intent classify result '%s' 未精确命中枚举，丢弃", raw)
            return None
        except Exception as e:
            logger.debug(f"LLM intent classify failed: {e}")
            return None


class EntityExtractor:
    """实体提取器: 从自然语言中提取查询实体。

    本体论原则（ADR-079 理解层）：
    - 规则提取优先（引号/「的」/大写英文），确定性。
    - LLM 实体提取是「选择」兜底：输出必须经 USL 术语归一化 + 本体实体集合过滤，
      未命中本体集合的候选**丢弃**（不采纳幻觉实体）。
    """

    def __init__(self, llm_client=None, term_resolver=None, entity_set=None):
        self.llm_client = llm_client
        self.term_resolver = term_resolver
        self.entity_set = entity_set  # 本体实体 canonical 集合（可选）

    def set_entity_context(self, term_resolver=None, entity_set=None) -> None:
        """注入本体上下文：USL 术语解析器 + 实体 canonical 集合"""
        self.term_resolver = term_resolver
        self.entity_set = entity_set

    def extract(self, query: str, domain_id: str = "") -> List[str]:
        """提取查询中的实体名（规则优先 + LLM 选择兜底，经本体归一化）。

        Args:
            query: 查询文本
            domain_id: 场景/领域编码（如 sanguo/xiyou）。归一化**仅在该领域内**查表，
                       跨场景不猜测。空串表示未指定场景（回退全领域）。
        """
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

        # LLM 选择兜底（仅当规则提取不足时）
        if len(entities) < 2 and self.llm_client:
            llm_entities = self._llm_extract(query)
            if llm_entities:
                entities.extend(llm_entities)

        # 归一化 + 去重 + 过滤（归一化限定在 domain_id 场景内）
        seen = set()
        result = []
        for e in entities:
            e = e.strip()
            if not e or e in seen or len(e) < 2:
                continue
            canonical = self._normalize_entity(e, domain_id)
            if canonical is None:
                # 未命中本体（LLM 幻觉 / 未知实体 / 非本场景）→ 丢弃，不采纳
                continue
            if canonical not in seen:
                seen.add(canonical)
                result.append(canonical)

        return result

    def _normalize_entity(self, entity: str, domain_id: str = "") -> Optional[str]:
        """将实体归一化到 canonical（场景内 USL 字典 / 本体集合校验）。

        - 无 term_resolver 且无 entity_set → 原词（未注入本体上下文时不做过滤）
        - 有 term_resolver → 在 domain_id 领域内归一化；canonical 不在 entity_set → None
        - 仅 entity_set → 精确命中才返回，否则 None
        """
        if self.term_resolver is not None:
            canonical = self.term_resolver.resolve(entity, domain_id=domain_id)
            if self.entity_set is not None:
                if canonical not in self.entity_set:
                    return None
            return canonical
        if self.entity_set is not None:
            return entity if entity in self.entity_set else None
        return entity

    def _llm_extract(self, query: str) -> Optional[List[str]]:
        """LLM 实体提取（「选择」：只产出候选，不保证正确，后续经本体归一化过滤）"""
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
        """分析查询: 意图识别 + 实体提取 + 澄清检测。

        context 可含 domain_id（场景/领域编码），用于实体归一化限定场景。
        """
        context = context or {}

        # 领域上下文（由编排层经 scenario→ontology→domain 权威链解析后注入）。
        # 理解层只认 domain_id，不做 scenario_id 反向解析（ADR-079 §7.3）。
        domain_id = context.get("domain_id") or ""

        # 共指消解
        context_entities = context.get("entities", [])
        resolved_query = self.entity_extractor.resolve_coreferences(query, context_entities)

        # 意图识别
        intent, confidence = self.intent_recognizer.recognize(resolved_query)

        # 实体提取（限定场景内归一化）
        entities = self.entity_extractor.extract(resolved_query, domain_id=domain_id)

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
