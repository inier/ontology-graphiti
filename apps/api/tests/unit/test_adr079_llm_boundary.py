"""TDD 单元测试：ADR-079 本体论与 LLM 结合边界（三层治理）。

验证：
  T-079-1: EntityExtractor 规则提取优先（确定性）
  T-079-2: EntityExtractor LLM 选择兜底 + USL 归一化（"老刘"→canonical）
  T-079-3: EntityExtractor 幻觉实体经本体过滤被丢弃（不采纳）
  T-079-4: EntityExtractor 未注入本体上下文 → 原词安全降级（不过滤）
  T-079-5: ResponseGenerator 事实锚定（合法引用通过）
  T-079-6: ResponseGenerator 编造来源编号 → 降级模板回答
  T-079-7: ResponseGenerator 无来源引用 → 降级模板回答
  T-079-8: IntentRecognizer LLM 选择兜底强校验（精确枚举否则丢弃）
"""

from __future__ import annotations

import pytest

from odap.biz.data.qa.pipeline.understanding.intent_recognizer import (
    EntityExtractor,
    IntentRecognizer,
)
from odap.biz.data.qa.pipeline.generation.response_generator import (
    ResponseGenerator,
)
from odap.biz.data.qa.models import (
    QueryIntent, QueryUnderstanding, RetrievalResultSet, RetrievalResult,
)
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)


class _FakeLLM:
    """可控 LLM：预设响应"""

    def __init__(self, response: str):
        self._response = response
        self.called = False

    def generate(self, prompt, max_tokens=32, timeout=5):
        self.called = True
        return self._response


# ── 实体提取（理解层）──

class TestEntityExtractor:
    def test_rule_extraction_priority(self):
        # 无 LLM，纯规则提取
        ext = EntityExtractor(llm_client=None)
        entities = ext.extract("查找「刘备」的关联人物")
        assert "刘备" in entities

    def test_llm_selection_normalized_within_domain(self):
        # LLM 提取"老刘"，在 sanguo 领域归一化到 canonical"刘备"
        resolver = UslTermResolver()
        resolver.load_terms("sanguo", [
            {"canonical": "刘备", "semantic_type": "人物",
             "synonyms": ["老刘", "刘玄德"], "near_synonyms": [], "aliases": [],
             "stoplist_flag": False},
        ])
        fake = _FakeLLM("老刘\n曹操")
        ext = EntityExtractor(llm_client=fake, term_resolver=resolver,
                              entity_set={"刘备", "曹操"})
        entities = ext.extract("老刘和曹操的关系", domain_id="sanguo")
        # "老刘" 在 sanguo 场景归一化为 "刘备"
        assert "刘备" in entities
        assert "曹操" in entities

    def test_same_word_different_domain(self):
        # 场景隔离：同一个"老刘"在不同领域归一化结果不同（不跨场景猜测）
        resolver = UslTermResolver()
        # sanguo: 老刘 → 刘备
        resolver.load_terms("sanguo", [
            {"canonical": "刘备", "semantic_type": "人物",
             "synonyms": ["老刘"], "near_synonyms": [], "aliases": [],
             "stoplist_flag": False},
        ])
        # xiyou: 无"老刘"术语
        resolver.load_terms("xiyou", [
            {"canonical": "唐僧", "semantic_type": "人物",
             "synonyms": [], "near_synonyms": [], "aliases": [],
             "stoplist_flag": False},
        ])
        fake = _FakeLLM("老刘")
        ext = EntityExtractor(llm_client=fake, term_resolver=resolver,
                              entity_set={"刘备", "唐僧"})

        # sanguo 场景：老刘 → 刘备
        sanguo_entities = ext.extract("老刘是谁", domain_id="sanguo")
        assert "刘备" in sanguo_entities
        assert "唐僧" not in sanguo_entities

        # xiyou 场景：老刘未命中（不归一化为刘备），且不在本体集合 → 丢弃
        xiyou_entities = ext.extract("老刘是谁", domain_id="xiyou")
        assert "刘备" not in xiyou_entities

    def test_hallucinated_entity_dropped(self):
        # LLM 提取幻觉实体（不在本体集合）→ 丢弃
        resolver = UslTermResolver()
        resolver.load_terms("sanguo", [
            {"canonical": "刘备", "semantic_type": "人物",
             "synonyms": [], "near_synonyms": [], "aliases": [],
             "stoplist_flag": False},
        ])
        fake = _FakeLLM("孙悟空")  # 幻觉实体（不在 sanguo 本体）
        ext = EntityExtractor(llm_client=fake, term_resolver=resolver,
                              entity_set={"刘备"})
        entities = ext.extract("孙悟空是谁", domain_id="sanguo")
        # 幻觉实体被过滤，规则也未命中 → 空
        assert "孙悟空" not in entities

    def test_no_ontology_context_safe_passthrough(self):
        # 未注入本体上下文 → 原词安全降级（不过滤，不误删）
        fake = _FakeLLM("刘备")
        ext = EntityExtractor(llm_client=fake)  # 无 term_resolver / entity_set
        entities = ext.extract("刘备是谁")
        assert "刘备" in entities


# ── 生成层（事实锚定）──

class TestResponseGenerator:
    def _result_set(self, n=3):
        results = [
            RetrievalResult(doc_id=f"d{i}", content=f"内容{i}",
                            score=0.9, pillar="graph", source="cypher")
            for i in range(1, n + 1)
        ]
        return RetrievalResultSet(results=results)

    def _understanding(self):
        return QueryUnderstanding(original_query="q", intent=QueryIntent.GRAPH_TRAVERSE)

    def test_valid_reference_accepted(self):
        fake = _FakeLLM("刘备与关羽是结义兄弟 [1]。")
        gen = ResponseGenerator(llm_client=fake)
        rs = self._result_set()
        answer = gen.generate("q", rs, self._understanding())
        # 合法引用 [1] → 采纳 LLM 回答
        assert "结义兄弟" in answer

    def test_fabricated_reference_downgrades(self):
        fake = _FakeLLM("刘备与关羽是结义兄弟 [99]。")  # 非法编号
        gen = ResponseGenerator(llm_client=fake)
        rs = self._result_set()
        answer = gen.generate("q", rs, self._understanding())
        # 非法引用 → 降级模板回答（含"检索到以下相关信息"）
        assert "检索到以下相关信息" in answer

    def test_no_reference_downgrades(self):
        fake = _FakeLLM("刘备与关羽是结义兄弟。")  # 无来源引用
        gen = ResponseGenerator(llm_client=fake)
        rs = self._result_set()
        answer = gen.generate("q", rs, self._understanding())
        # 无引用 → 降级模板回答
        assert "检索到以下相关信息" in answer


# ── 意图分发（理解层 LLM 选择兜底）──

class TestIntentSelection:
    def test_llm_selection_exact_enum(self):
        fake = _FakeLLM("graph_traverse")
        rec = IntentRecognizer(llm_client=fake)
        # 构造平局（"查找"=keyword_lookup + "关联"=graph_traverse）
        intent, _ = rec.recognize("查找A关联B")
        assert intent == QueryIntent.GRAPH_TRAVERSE

    def test_llm_selection_invalid_discarded(self):
        fake = _FakeLLM("这是一个复杂的分析型查询")
        rec = IntentRecognizer(llm_client=fake)
        intent, _ = rec.recognize("查找A关联B")
        # 非精确枚举 → 丢弃，回退规则平局首个
        assert intent in (QueryIntent.KEYWORD_LOOKUP, QueryIntent.GRAPH_TRAVERSE)
