"""Unit tests for NLDispatcher."""
import asyncio
import sys
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock

import pytest

from odap.biz.core.ontology.application.query_api.nl_dispatcher import NLDispatcher
from odap.biz.core.ontology.application.query_api.intent_classifier import QueryIntent


def _make_query_result(source="entity", rows=None):
    qr = MagicMock()
    qr.source.value = source
    qr.rows = rows or [{"id": "a", "score": 0.9}]
    qr.total = len(rows or [])
    return qr


def _inject_graphiti_mock():
    """注入 graphiti_core mock 模块到 sys.modules，解决测试环境无 graphiti_core 的问题。"""
    mock_message = MagicMock()
    mock_message.side_effect = lambda **kwargs: MagicMock(**kwargs)
    mock_models = MagicMock()
    mock_models.Message = mock_message
    mock_prompts = MagicMock()
    mock_prompts.models = mock_models
    mock_core = MagicMock()
    mock_core.prompts = mock_prompts
    # 强制覆盖，不用 setdefault（其他测试可能设置了不兼容的 mock）
    sys.modules["graphiti_core"] = mock_core
    sys.modules["graphiti_core.prompts"] = mock_prompts
    sys.modules["graphiti_core.prompts.models"] = mock_models


class TestNLDispatcher:
    def test_singleton(self):
        a = NLDispatcher.get_instance()
        b = NLDispatcher.get_instance()
        assert a is b

    @pytest.mark.asyncio
    async def test_dispatch_structured(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute_async = AsyncMock(return_value=_make_query_result("entity"))
            result = await dispatcher.dispatch("查询所有 person 类型实体", workspace_id="ws-1")
            assert result["status"] == "success"
            assert result["intent"] == QueryIntent.STRUCTURED.value
            assert result["source"] == "entity"
            assert "translated_dsl" in result

    @pytest.mark.asyncio
    async def test_dispatch_unstructured_keyword(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute_async = AsyncMock(return_value=_make_query_result("unstructured", [{"content": "doc"}]))
            result = await dispatcher.dispatch("查询相关文档", workspace_id="ws-1")
            assert result["intent"] == QueryIntent.UNSTRUCTURED.value
            assert ".unstructured" in result["translated_dsl"]

    @pytest.mark.asyncio
    async def test_dispatch_hybrid(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute_async = AsyncMock(side_effect=[
                _make_query_result("entity", [{"id": "1", "score": 0.9}]),
                _make_query_result("unstructured", [{"id": "2", "score": 0.7}]),
            ])
            result = await dispatcher.dispatch(
                "查询实体和相关文档", workspace_id="ws-1",
            )
            assert result["intent"] == QueryIntent.HYBRID.value
            assert result["total"] == 2
            assert "structured_count" in result
            assert "unstructured_count" in result

    @pytest.mark.asyncio
    async def test_dispatch_action_no_skills(self):
        dispatcher = NLDispatcher()
        with patch(
            "odap.biz.core.ontology.application.query_api.nl_dispatcher.get_app_skill_registry"
        ) as mock_reg_factory:
            mock_reg = MagicMock()
            mock_reg.list.return_value = []
            mock_reg_factory.return_value = mock_reg
            result = await dispatcher.dispatch("执行这个动作", workspace_id="ws-1", ontology_id="ont-1")
            assert result["status"] == "error"
            assert "no app skills" in result["message"]

    @pytest.mark.asyncio
    async def test_dispatch_force_intent(self):
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_query_service") as mock_qs:
            mock_qs.execute_async = AsyncMock(return_value=_make_query_result("unstructured"))
            result = await dispatcher.dispatch(
                "anything", workspace_id="ws-1", hints={"force_intent": "unstructured"},
            )
            assert result["intent"] == QueryIntent.UNSTRUCTURED.value

    @pytest.mark.asyncio
    async def test_dispatch_empty_query(self):
        dispatcher = NLDispatcher()
        result = await dispatcher.dispatch("", workspace_id="ws-1")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_nl_to_dsl_topo(self):
        dispatcher = NLDispatcher()
        # LLM 不可用时回退到关键词
        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None):
            dsl = await dispatcher._nl_to_dsl("查询 X 的邻居", ontology_id="ont-1")
        assert ".topo" in dsl

    @pytest.mark.asyncio
    async def test_nl_to_dsl_temporal(self):
        dispatcher = NLDispatcher()
        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None):
            dsl = await dispatcher._nl_to_dsl("查询历史变更", ontology_id="ont-1")
        assert ".temporal" in dsl

    @pytest.mark.asyncio
    async def test_nl_to_dsl_schema(self):
        dispatcher = NLDispatcher()
        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None):
            dsl = await dispatcher._nl_to_dsl("查询 person 类型定义", ontology_id="ont-1")
        assert ".schema" in dsl

    @pytest.mark.asyncio
    async def test_nl_to_dsl_default(self):
        dispatcher = NLDispatcher()
        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None):
            dsl = await dispatcher._nl_to_dsl("随便查查", ontology_id="ont-1")
        assert ".entity" in dsl
        assert "ontology_id='ont-1'" in dsl


class TestNLToDSLWithKeywords:
    """测试关键词启发式回退逻辑。"""

    def test_neighbors_keyword(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("查询 X 的邻居", ontology_id=None)
        assert ".topo" in dsl
        assert "neighbors" in dsl

    def test_path_keyword(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("从 A 到 B 的路径", ontology_id=None)
        assert ".topo" in dsl
        assert "path" in dsl

    def test_history_keyword(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("历史变更记录", ontology_id=None)
        assert ".temporal" in dsl
        assert "history" in dsl

    def test_schema_keyword(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("查看类型定义", ontology_id=None)
        assert ".schema" in dsl

    def test_default_entity_search(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("随便查查", ontology_id="ont-1")
        assert ".entity" in dsl
        assert "ontology_id='ont-1'" in dsl

    def test_default_entity_no_ontology(self):
        dispatcher = NLDispatcher()
        dsl = dispatcher._nl_to_dsl_with_keywords("随便查查", ontology_id=None)
        assert ".entity" in dsl
        assert "ontology_id" not in dsl


class TestNLToDSLWithLLM:
    """测试 LLM 增强 NL->DSL 转换。"""

    @pytest.fixture(autouse=True)
    def _setup_graphiti_mock(self):
        """确保 graphiti_core mock 已注入。"""
        _inject_graphiti_mock()

    @pytest.mark.asyncio
    async def test_llm_returns_none_when_no_client(self):
        """LLM 客户端不可用时返回 None。"""
        dispatcher = NLDispatcher()
        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None):
            result = await dispatcher._nl_to_dsl_with_llm("查找所有装备", ontology_id=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_valid_dsl_accepted(self):
        """LLM 返回合法 DSL（以 . 开头）时被接受。"""
        dispatcher = NLDispatcher()
        mock_client = MagicMock()

        async def _fake_generate(messages, max_tokens=256):
            return {"response": ".entity with(type='装备') list()"}, 10, 5

        mock_client._generate_response = _fake_generate

        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=mock_client):
            result = await dispatcher._nl_to_dsl_with_llm("查找所有装备", ontology_id=None)
        assert result == ".entity with(type='装备') list()"

    @pytest.mark.asyncio
    async def test_llm_dsl_with_code_block(self):
        """LLM 返回 markdown 代码块包裹的 DSL 时正确提取。"""
        dispatcher = NLDispatcher()
        mock_client = MagicMock()

        async def _fake_generate(messages, max_tokens=256):
            return {"response": "```\n.topo neighbors(XX)\n```"}, 10, 5

        mock_client._generate_response = _fake_generate

        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=mock_client):
            result = await dispatcher._nl_to_dsl_with_llm("XX的邻居", ontology_id=None)
        assert result == ".topo neighbors(XX)"

    @pytest.mark.asyncio
    async def test_llm_invalid_dsl_rejected(self):
        """LLM 返回不以 . 开头的输出时返回 None（回退到关键词）。"""
        dispatcher = NLDispatcher()
        mock_client = MagicMock()

        async def _fake_generate(messages, max_tokens=256):
            return {"response": "This is not a valid DSL"}, 10, 5

        mock_client._generate_response = _fake_generate

        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=mock_client):
            result = await dispatcher._nl_to_dsl_with_llm("查找所有装备", ontology_id=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self):
        """LLM 调用异常时返回 None。"""
        dispatcher = NLDispatcher()
        mock_client = MagicMock()

        async def _fake_generate(messages, max_tokens=256):
            raise RuntimeError("API error")

        mock_client._generate_response = _fake_generate

        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=mock_client):
            result = await dispatcher._nl_to_dsl_with_llm("查找所有装备", ontology_id=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_nl_to_dsl_fallback_to_keywords(self):
        """LLM 失败时回退到关键词启发式。"""
        dispatcher = NLDispatcher()
        with patch.object(
            type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=None
        ):
            dsl = await dispatcher._nl_to_dsl("查询 X 的邻居", ontology_id="ont-1")
        assert ".topo" in dsl
        assert "neighbors" in dsl

    @pytest.mark.asyncio
    async def test_nl_to_dsl_prefers_llm(self):
        """LLM 可用时优先使用 LLM 结果。"""
        dispatcher = NLDispatcher()
        with patch.object(
            dispatcher, "_nl_to_dsl_with_llm", new_callable=AsyncMock, return_value=".topo neighbors(X)"
        ):
            dsl = await dispatcher._nl_to_dsl("X的邻居", ontology_id=None)
        assert dsl == ".topo neighbors(X)"

    @pytest.mark.asyncio
    async def test_nl_to_dsl_llm_none_falls_back(self):
        """LLM 返回 None 时回退到关键词。"""
        dispatcher = NLDispatcher()
        with patch.object(dispatcher, "_nl_to_dsl_with_llm", new_callable=AsyncMock, return_value=None):
            dsl = await dispatcher._nl_to_dsl("查询 X 的邻居", ontology_id="ont-1")
        assert ".topo" in dsl
        assert "neighbors" in dsl

    @pytest.mark.asyncio
    async def test_llm_with_ontology_id_hint(self):
        """LLM 调用时 ontology_id 被传入 user prompt。"""
        dispatcher = NLDispatcher()
        mock_client = MagicMock()
        captured_messages = []

        async def _fake_generate(messages, max_tokens=256):
            captured_messages.extend(messages)
            return {"response": ".entity with(type='装备', ontology_id='ont-1') list()"}, 10, 5

        mock_client._generate_response = _fake_generate

        with patch.object(type(dispatcher), "_llm_client", new_callable=PropertyMock, return_value=mock_client):
            result = await dispatcher._nl_to_dsl_with_llm("查找所有装备", ontology_id="ont-1")
        assert result is not None
        # 验证 user message 包含 ontology_id
        user_msg = captured_messages[-1].content
        assert "ont-1" in user_msg


class TestLLMClientProperty:
    """测试 LLM 客户端懒加载属性。"""

    def test_no_api_key_returns_none(self):
        """无 OPENAI_API_KEY 时返回 None。"""
        dispatcher = NLDispatcher()
        with patch.dict("os.environ", {}, clear=True):
            # 重置缓存
            dispatcher._llm_client_cache = None
            result = dispatcher._llm_client
        assert result is None

    def test_import_failure_returns_none(self):
        """ZhipuAIClient 导入失败时返回 None。"""
        dispatcher = NLDispatcher()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            dispatcher._llm_client_cache = None
            # 让 import 语句失败
            with patch.dict("sys.modules", {"odap.infra.llm.llm_service": None}):
                result = dispatcher._llm_client
        assert result is None
