"""Unit tests for NLDispatcher."""
from unittest.mock import patch, MagicMock

import pytest

from odap.biz.core.ontology.application.query_api.nl_dispatcher import NLDispatcher
from odap.biz.core.ontology.application.query_api.intent_classifier import QueryIntent


def _make_query_result(source="entity", rows=None):
    qr = MagicMock()
    qr.source.value = source
    qr.rows = rows or [{"id": "a", "score": 0.9}]
    qr.total = len(rows or [])
    return qr


class TestNLDispatcher:
    def test_singleton(self):
        a = NLDispatcher.get_instance()
        b = NLDispatcher.get_instance()
        assert a is b

    def test_dispatch_structured(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute.return_value = _make_query_result("entity")
            result = dispatcher.dispatch("查询所有 person 类型实体", workspace_id="ws-1")
            assert result["status"] == "success"
            assert result["intent"] == QueryIntent.STRUCTURED.value
            assert result["source"] == "entity"
            assert "translated_dsl" in result

    def test_dispatch_unstructured_keyword(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute.return_value = _make_query_result("unstructured", [{"content": "doc"}])
            result = dispatcher.dispatch("查询相关文档", workspace_id="ws-1")
            assert result["intent"] == QueryIntent.UNSTRUCTURED.value
            assert ".unstructured" in result["translated_dsl"]

    def test_dispatch_hybrid(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute.side_effect = [
                _make_query_result("entity", [{"id": "1", "score": 0.9}]),
                _make_query_result("unstructured", [{"id": "2", "score": 0.7}]),
            ]
            result = dispatcher.dispatch(
                "查询实体和相关文档", workspace_id="ws-1",
            )
            assert result["intent"] == QueryIntent.HYBRID.value
            assert result["total"] == 2
            assert "structured_count" in result
            assert "unstructured_count" in result

    def test_dispatch_action_no_skills(self):
        dispatcher = NLDispatcher()
        with patch(
            "odap.biz.core.ontology.application.query_api.nl_dispatcher.get_app_skill_registry"
        ) as mock_reg_factory:
            mock_reg = MagicMock()
            mock_reg.list.return_value = []
            mock_reg_factory.return_value = mock_reg
            result = dispatcher.dispatch("执行这个动作", workspace_id="ws-1", ontology_id="ont-1")
            assert result["status"] == "error"
            assert "no app skills" in result["message"]

    def test_dispatch_force_intent(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute.return_value = _make_query_result("unstructured")
            result = dispatcher.dispatch(
                "anything", workspace_id="ws-1", hints={"force_intent": "unstructured"},
            )
            assert result["intent"] == QueryIntent.UNSTRUCTURED.value

    def test_dispatch_empty_query(self):
        dispatcher = NLDispatcher()
        result = dispatcher.dispatch("", workspace_id="ws-1")
        assert result["status"] == "error"

    def test_nl_to_dsl_topo(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl("查询 X 的邻居", ontology_id="ont-1")
        assert ".topo" in dsl

    def test_nl_to_dsl_temporal(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl("查询历史变更", ontology_id="ont-1")
        assert ".temporal" in dsl

    def test_nl_to_dsl_schema(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl("查询 person 类型定义", ontology_id="ont-1")
        assert ".schema" in dsl

    def test_nl_to_dsl_default(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl("随便查查", ontology_id="ont-1")
        assert ".entity" in dsl
        assert "ontology_id='ont-1'" in dsl
