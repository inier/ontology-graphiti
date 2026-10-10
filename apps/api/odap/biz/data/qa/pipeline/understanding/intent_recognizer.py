"""Stage 1: 查询理解 - 意图识别 + 实体提取 + 查询改写

本体论原则（严格）：
- 意图识别是**意图分发**：把自然语言映射到 QueryIntent 枚举（closed set）。
- 规则是**权威**（确定性），LLM 仅在规则无法区分（多规则同权重）时兜底。
- LLM 兜底结果必须**强校验**落在枚举内，否则丢弃（宁可 unknown 也不幻觉）。
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import QueryIntent, QueryUnderstanding
from odap.biz.data.qa.pipeline.understanding.extractor_mode import (
    resolve_extractor_mode,
)

logger = logging.getLogger(__name__)

# ── 意图规则 ──────────────────────────────────────────────────────────

_INTENT_RULES: List[tuple] = [
    # (意图, 正则, 权重)
    (QueryIntent.KEYWORD_LOOKUP, re.compile(r'查找|查询|检索|搜索|找到|有没有|是否包含|精确匹配|叫什么'), 0.8),
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


class SemanticsProvider:
    """按需查询本体语义（同步）——query 模式的查询后端（ADR-089 C-D3/C-D4）。

    「查询优于注入」：每次只查当前 expression 对应的 USL 术语，不预加载全量字典。
    查询经 allowed 路径（semantic_admin.usl_manager），不深插 ontology 内部（C3）。
    失败绝不抛：返回 canonical=None（由调用方决定兜底，规则 14）。
    """

    def __init__(self, query_fn=None):
        # query_fn(expression, domain_id, kinds) -> {"content": {...}}；测试可注入
        self._query_fn = query_fn

    def query(self, expression: str, domain_id: str = "",
              kinds=("content",)) -> Dict[str, Any]:
        if self._query_fn is not None:
            return self._query_fn(expression, domain_id, list(kinds))
        try:
            from odap.biz.semantic_admin.usl_manager.services import (
                UslManagerService,
            )
            res = UslManagerService().list_terms(
                domain_id=domain_id or None,
                synonym_keyword=expression, page_size=5)
            items = (res or {}).get("items", []) if isinstance(res, dict) else []
        except Exception as e:  # 规则 14：可观测降级
            logger.warning("SemanticsProvider 查询失败(%s): %s", expression, e)
            items = []
        if not items:
            return {"content": {"canonical": None}}
        t = items[0]
        return {"content": {
            "canonical": t.get("canonical"),
            "synonyms": list(t.get("synonyms") or []),
            "near_synonyms": list(t.get("near_synonyms") or []),
            "semantic_type": t.get("semantic_type"),
            "domain_id": t.get("domain_id"),
        }}


class EntityExtractor:
    """实体提取器: 从自然语言中提取查询实体。

    本体论原则（ADR-079 理解层）：
    - 规则提取优先（引号/「的」/大写英文），确定性。
    - LLM 实体提取是「选择」兜底：输出必须经 USL 术语归一化 + 本体实体集合过滤，
      未命中本体集合的候选**丢弃**（不采纳幻觉实体）。

    三模式（ADR-089）：
    - off：原词直通（历史行为，可回滚）
    - inject：预加载 term_resolver + entity_set 后注入（对照/兼容）
    - query：按需查询（SemanticsProvider），归一化 + 幻觉过滤（默认）
    """

    def __init__(self, llm_client=None, term_resolver=None, entity_set=None,
                 mode: Optional[str] = None, semantics_provider=None):
        self.llm_client = llm_client
        self.term_resolver = term_resolver
        self.entity_set = entity_set  # 本体实体 canonical 集合（可选）
        # mode 未显式指定 → 按注入的上下文推导（保持 ADR-079 历史行为，零回归）：
        #   注入 term_resolver / entity_set → inject（领域内归一化 + 本体集合过滤）
        #   两者皆无                        → off（原词安全直通，不过滤不误删）
        # 显式 mode= 或 set_entity_context(mode=...) 时以显式为准（ADR-089 三模式）。
        self.mode = mode or (
            "inject"
            if (term_resolver is not None or entity_set is not None)
            else "off"
        )
        self.semantics_provider = semantics_provider
        self._cache: Dict[tuple, Optional[str]] = {}

    def set_entity_context(self, term_resolver=None, entity_set=None, *,
                           mode: Optional[str] = None,
                           semantics_provider=None) -> None:
        """注入本体上下文：USL 术语解析器 + 实体 canonical 集合（inject 模式）。

        mode 缺省走三级解析（sa_config > env > query）。
        """
        self.mode = mode or resolve_extractor_mode()
        if self.mode == "inject":
            self.term_resolver = term_resolver
            self.entity_set = entity_set
            self.semantics_provider = None
        elif self.mode == "query":
            self.term_resolver = None
            self.entity_set = None
            self.semantics_provider = semantics_provider or SemanticsProvider()
            self._cache = {}
        else:  # off
            self.term_resolver = None
            self.entity_set = None
            self.semantics_provider = None

    def extract(self, query: str, domain_id: str = "") -> List[str]:
        """提取查询中的实体名（规则优先 + LLM 选择兜底，经本体归一化）。

        Args:
            query: 查询文本
            domain_id: 场景/领域编码（如 sanguo/xiyou）。归一化**仅在该领域内**查表，
                       跨场景不猜测。空串表示未指定场景（回退全领域）。
        """
        entities: List[str] = []
        self._cache = {}   # query 模式：per-extract 缓存（ADR-089 C-D10）

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
                from odap.biz.semantic_admin.gap_pool.services.gap_emitter import report_gap_signal
                from odap.biz.semantic_admin.gap_pool.models import GapLayer, GapSignalSource
                report_gap_signal(
                    GapSignalSource.MAPPING_FAILURE, e,
                    domain_id=domain_id,
                    detail="未命中本体集合，丢弃", ref="intent_recognizer",
                    attribution={"layer": GapLayer.CONTENT.value,
                                 "target_kind": "term", "target_ref": e},
                )
                continue
            if canonical not in seen:
                seen.add(canonical)
                result.append(canonical)

        return result

    def _normalize_entity(self, entity: str, domain_id: str = "") -> Optional[str]:
        """将实体归一化到 canonical（三模式分派，ADR-089）。

        - off    → 原词直通（历史行为）
        - inject → 领域内 USL 归一化 + entity_set 集合过滤
        - query  → 按需查询（SemanticsProvider）：命中 canonical 采纳，未命中 None
        """
        if self.mode == "off":
            return entity
        if self.mode == "inject":
            return self._normalize_inject(entity, domain_id)
        return self._normalize_query(entity, domain_id)

    def _normalize_inject(self, entity: str, domain_id: str) -> Optional[str]:
        """inject 模式：预加载 USL 字典 + 实体集合过滤。"""
        if self.term_resolver is not None:
            canonical = self.term_resolver.resolve(entity, domain_id=domain_id)
            if self.entity_set is not None:
                if canonical not in self.entity_set:
                    return None
            return canonical
        if self.entity_set is not None:
            return entity if entity in self.entity_set else None
        return entity

    def _normalize_query(self, entity: str, domain_id: str) -> Optional[str]:
        """query 模式：按需查询本体语义（per-extract 缓存；失败原词兜底）。"""
        key = (entity, domain_id)
        if key in self._cache:
            return self._cache[key]
        provider = self.semantics_provider or SemanticsProvider()
        t0 = time.perf_counter()
        try:
            r = provider.query(entity, domain_id=domain_id, kinds=["content"])
        except Exception as e:  # 客户端侧兜底（规则 14）
            logger.warning("ontology_semantics 调用失败(%s): %s", entity, e)
            self._record_cost(entity, domain_id, round_trips=1,
                              wall_ms=(time.perf_counter() - t0) * 1000.0,
                              error=str(e))
            return entity
        canonical = (r or {}).get("content", {}).get("canonical")
        self._cache[key] = canonical
        self._record_cost(entity, domain_id, round_trips=1,
                          wall_ms=(time.perf_counter() - t0) * 1000.0, error=None)
        return canonical

    @staticmethod
    def _record_cost(entity: str, domain_id: str, *, round_trips: int,
                     wall_ms: float, error) -> None:
        """成本对账（ADR-089 C-D5）。热路径默认关闭，COST_AUDIT_ENABLED=1 时开启。

        DB 写入绝不阻塞/破坏提取：任何异常吞为 debug（规则 14.6 边界）。
        """
        if os.environ.get("COST_AUDIT_ENABLED") != "1":
            return
        try:
            from odap.biz.data.qa.evaluation.cost_audit import CostAuditStorage
            CostAuditStorage().record(
                call_kind="entity_extract", mode="query",
                scope_key=f"{domain_id or '-'}", expression=entity,
                cost={"round_trips": round_trips, "wall_ms": round(wall_ms, 3),
                      "error": error},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("cost_audit 记录失败（不影响提取）：%s", e)

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
        # ADR-089 C-D14：生产接线——按运行时配置（默认 query）启用按需查询归一化。
        # 此前 set_entity_context 从未被调用，实体归一化在生产形同虚设。
        self.entity_extractor.set_entity_context(mode=resolve_extractor_mode())

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
