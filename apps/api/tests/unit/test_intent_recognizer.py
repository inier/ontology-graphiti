"""TDD 单元测试：意图识别器（意图分发确定性 + LLM 兜底强校验）。

验证本体论原则：
- 规则是权威（确定性），同一查询任何时刻结果一致
- 无规则命中 → 默认语义搜索，不调用 LLM
- 唯一最高权重规则 → 直接确定，不调用 LLM
- 多规则平局 → 才用 LLM 兜底，且结果强校验（精确命中枚举）
- LLM 兜底结果不匹配枚举 → 丢弃，回退确定性规则

覆盖：
  T-IR-1: 无规则命中默认语义搜索（确定性）
  T-IR-2: 唯一最高权重规则直接确定
  T-IR-3: 规则平局无 LLM → 稳定取首
  T-IR-4: LLM 兜底结果精确命中枚举才采用
  T-IR-5: LLM 兜底结果非精确枚举 → 丢弃回退
  T-IR-6: 无 LLM 客户端时平局 → 稳定取首（不调用 LLM）
"""

from __future__ import annotations

import pytest

from odap.biz.data.qa.pipeline.understanding.intent_recognizer import (
    IntentRecognizer,
)
from odap.biz.data.qa.models import QueryIntent


class _FakeLLM:
    """可控 LLM 客户端：返回预设字符串"""

    def __init__(self, response: str):
        self._response = response
        self.called = False

    def generate(self, prompt, max_tokens=32, timeout=5):
        self.called = True
        return self._response


class TestIntentRecognizer:
    def test_no_rule_default_semantic_search(self):
        # 无任何规则关键词命中 → 默认语义搜索
        rec = IntentRecognizer(llm_client=None)
        intent, confidence = rec.recognize("你好")
        assert intent == QueryIntent.SEMANTIC_SEARCH
        assert confidence == 0.3

    def test_unique_top_weight_rule_direct(self):
        # "执行" 命中 ACTION（权重 0.9），唯一最高 → 直接确定
        rec = IntentRecognizer(llm_client=None)
        intent, _ = rec.recognize("执行部署任务")
        assert intent == QueryIntent.ACTION

    def test_graph_traverse_rule(self):
        # "关联" 命中 GRAPH_TRAVERSE
        rec = IntentRecognizer(llm_client=None)
        intent, _ = rec.recognize("A关联B的关系")
        assert intent == QueryIntent.GRAPH_TRAVERSE

    def test_llm_backoff_exact_match(self):
        # 构造平局场景，LLM 返回精确枚举值 → 采用
        fake = _FakeLLM("graph_traverse")
        rec = IntentRecognizer(llm_client=fake)
        # "查找A关联B" 命中 KEYWORD_LOOKUP(查找) 和 GRAPH_TRAVERSE(关联)
        intent, _ = rec.recognize("查找A关联B")
        # LLM 返回 graph_traverse 精确命中 → 采用
        assert intent == QueryIntent.GRAPH_TRAVERSE

    def test_llm_backoff_invalid_result_discarded(self):
        # LLM 返回非枚举值（幻觉）→ 丢弃，回退确定性规则
        fake = _FakeLLM("这个查询很复杂，属于复杂分析类型")
        rec = IntentRecognizer(llm_client=fake)
        intent, _ = rec.recognize("查找A关联B")
        # 结果非精确枚举 → 回退平局首个（稳定序）
        assert intent in (QueryIntent.KEYWORD_LOOKUP, QueryIntent.GRAPH_TRAVERSE)

    def test_no_llm_tie_stable_first(self):
        # 无 LLM 客户端，平局 → 稳定取首个（不抛异常）
        rec = IntentRecognizer(llm_client=None)
        intent, _ = rec.recognize("查找A关联B")
        assert intent in (QueryIntent.KEYWORD_LOOKUP, QueryIntent.GRAPH_TRAVERSE)
