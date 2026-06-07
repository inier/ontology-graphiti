"""Unit tests for IntentClassifier and ResultMerger."""
import pytest

from odap.biz.core.ontology.application.query_api.intent_classifier import (
    IntentClassifier, QueryIntent,
)
from odap.biz.core.ontology.application.query_api.result_merger import merge as merge_results


class TestIntentClassifier:
    def test_action_keyword(self):
        c = IntentClassifier()
        assert c.classify("执行这个动作") == QueryIntent.ACTION
        assert c.classify("创建会话") == QueryIntent.ACTION

    def test_unstructured_keyword(self):
        c = IntentClassifier()
        assert c.classify("查找相关文档") == QueryIntent.UNSTRUCTURED
        assert c.classify("什么是 ontology") == QueryIntent.UNSTRUCTURED

    def test_hybrid_keyword(self):
        c = IntentClassifier()
        assert c.classify("查找实体和它的相关文档") == QueryIntent.HYBRID

    def test_default_structured(self):
        c = IntentClassifier()
        assert c.classify("查询所有 type=person 的实体") == QueryIntent.STRUCTURED

    def test_force_intent(self):
        c = IntentClassifier()
        assert c.classify("anything", hints={"force_intent": "action"}) == QueryIntent.ACTION

    def test_empty_query(self):
        c = IntentClassifier()
        assert c.classify("") == QueryIntent.UNKNOWN
        assert c.classify("   ") == QueryIntent.UNKNOWN

    def test_with_llm_provider(self):
        def fake_llm(prompt):
            return "unstructured"
        c = IntentClassifier(llm_provider=fake_llm)
        assert c.classify("random text with no keywords") == QueryIntent.UNSTRUCTURED

    def test_llm_provider_fallback(self):
        def fake_llm(prompt):
            return "garbage"
        c = IntentClassifier(llm_provider=fake_llm)
        # Falls back to default
        assert c.classify("random text") == QueryIntent.STRUCTURED

    def test_llm_provider_exception(self):
        def fake_llm(prompt):
            raise RuntimeError("LLM down")
        c = IntentClassifier(llm_provider=fake_llm)
        assert c.classify("random text") == QueryIntent.STRUCTURED


class TestResultMerger:
    def test_empty(self):
        assert merge_results([], []) == []

    def test_structured_only(self):
        rows = [{"id": "a", "score": 0.8}, {"id": "b", "score": 0.5}]
        merged = merge_results(rows, [])
        assert len(merged) == 2
        assert all("_source" in r for r in merged)

    def test_unstructured_only(self):
        rows = [{"id": "a", "score": 0.7, "content": "doc"}]
        merged = merge_results([], rows)
        assert len(merged) == 1
        assert merged[0]["_source"] == "unstructured"

    def test_merge_same_id(self):
        s = [{"id": "a", "score": 0.8, "name": "Alice"}]
        u = [{"id": "a", "score": 0.6, "content": "doc about a"}]
        merged = merge_results(s, u)
        assert len(merged) == 1
        assert merged[0]["id"] == "a"
        assert merged[0]["_score"] == 0.8
        assert "_sources" in merged[0]

    def test_merge_different_ids(self):
        s = [{"id": "a", "score": 0.8}]
        u = [{"id": "b", "score": 0.7}]
        merged = merge_results(s, u)
        assert len(merged) == 2
        # Sorted by score descending
        assert merged[0]["id"] == "a"
        assert merged[1]["id"] == "b"

    def test_max_size_limit(self):
        s = [{"id": f"a{i}", "score": 0.1 * i} for i in range(10)]
        merged = merge_results(s, [], max_size=5)
        assert len(merged) == 5

    def test_anon_rows(self):
        s = [{"name": "no-id"}]
        u = [{"content": "no-id either"}]
        merged = merge_results(s, u)
        assert len(merged) == 2
