"""Iter 4.2: AG-UI retrieval adapter + query_audit 埋点 + SSE tests.

Tests cover:
- RetrievalAGUIAdapter.stream_search: event sequence, low confidence Interrupt,
  service unavailable, query_audit 埋点
- RetrievalAGUIAdapter.stream_chain_search: STEP events, cycle detection Interrupt
- RetrievalAGUIAdapter helpers: _format_search_result, _check_confidence, _chunk_text
- Routes query_audit 埋点: each endpoint calls query_audit
- SSE streaming endpoints return StreamingResponse
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchResult
from odap.infra.openharness.agui.retrieval_adapter import (
    CONFIDENCE_THRESHOLD,
    RetrievalAGUIAdapter,
    get_retrieval_agui_adapter,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_search_result(
    total=2,
    rows=None,
    mode="nl",
    confidence=None,
):
    """构造 SearchResult mock。"""
    if rows is None:
        rows = [
            {"id": "e1", "name": "Entity1", "summary": "summary1", "confidence": 0.9},
            {"id": "e2", "name": "Entity2", "summary": "summary2", "confidence": 0.8},
        ]
    if confidence is not None:
        rows = [{"id": f"e{i}", "name": f"E{i}", "confidence": confidence} for i in range(total)]
    return SearchResult(query="test", mode=mode, total=total, rows=rows)


def _make_mock_service(search_result=None, chain_result=None):
    """构造 mock RetrievalService。"""
    service = MagicMock()
    if search_result is not None:
        service.search = AsyncMock(return_value=search_result)
    if chain_result is not None:
        service.chain_search = AsyncMock(return_value=chain_result)
    return service


# ------------------------------------------------------------------
# RetrievalAGUIAdapter.stream_search
# ------------------------------------------------------------------


class TestStreamSearch:
    @pytest.mark.asyncio
    async def test_emits_run_started_first(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test query"):
            events.append(event)

        assert events[0]["type"] == "RUN_STARTED"
        assert events[0]["input"]["query"] == "test query"

    @pytest.mark.asyncio
    async def test_emits_run_finished_last(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test query"):
            events.append(event)

        assert events[-1]["type"] == "RUN_FINISHED"
        assert events[-1]["outcome"]["type"] == "success"

    @pytest.mark.asyncio
    async def test_event_sequence_complete(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test query"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "RUN_STARTED" in types
        assert "STEP_STARTED" in types
        assert "TEXT_MESSAGE_START" in types
        assert "TEXT_MESSAGE_CONTENT" in types
        assert "TEXT_MESSAGE_END" in types
        assert "STEP_FINISHED" in types
        assert "RUN_FINISHED" in types

        # Verify order: RUN_STARTED before STEP_STARTED before TEXT_MESSAGE
        assert types.index("RUN_STARTED") < types.index("STEP_STARTED")
        assert types.index("STEP_STARTED") < types.index("TEXT_MESSAGE_START")
        assert types.index("TEXT_MESSAGE_END") < types.index("STEP_FINISHED")
        assert types.index("STEP_FINISHED") < types.index("RUN_FINISHED")

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_interrupt(self):
        """Results with confidence < threshold should trigger HITL Interrupt."""
        result = _make_search_result(total=3, confidence=0.2)  # below 0.5
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(
            retrieval_service=service, confidence_threshold=0.5
        )

        events = []
        async for event in adapter.stream_search("ws1", "test"):
            events.append(event)

        run_finished = events[-1]
        assert run_finished["type"] == "RUN_FINISHED"
        assert run_finished["outcome"]["type"] == "interrupt"
        assert len(run_finished["outcome"]["interrupts"]) == 1
        interrupt = run_finished["outcome"]["interrupts"][0]
        assert interrupt["reason"] == "confirmation"
        assert "低置信度" in interrupt["message"]

    @pytest.mark.asyncio
    async def test_high_confidence_no_interrupt(self):
        result = _make_search_result(total=2, confidence=0.9)
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test"):
            events.append(event)

        run_finished = events[-1]
        assert run_finished["outcome"]["type"] == "success"

    @pytest.mark.asyncio
    async def test_service_unavailable_emits_error(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=None)
        # Force _get_service to return None
        with patch.object(adapter, "_get_service", return_value=None):
            events = []
            async for event in adapter.stream_search("ws1", "test"):
                events.append(event)

        # Should emit RUN_STARTED then RUN_ERROR
        types = [e["type"] for e in events]
        assert "RUN_STARTED" in types
        assert "RUN_ERROR" in types

    @pytest.mark.asyncio
    async def test_search_exception_emits_error(self):
        service = MagicMock()
        service.search = AsyncMock(side_effect=RuntimeError("search failed"))
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "RUN_ERROR" in types

    @pytest.mark.asyncio
    async def test_search_exception_emits_step_finished_before_error(self):
        """M3 修复：检索异常时 STEP_FINISHED 必须在 RUN_ERROR 之前（AG-UI 协议一致性）。"""
        service = MagicMock()
        service.search = AsyncMock(side_effect=RuntimeError("search failed"))
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "STEP_STARTED" in types
        assert "STEP_FINISHED" in types
        assert "RUN_ERROR" in types
        # STEP_FINISHED 必须在 RUN_ERROR 之前
        assert types.index("STEP_FINISHED") < types.index("RUN_ERROR")

    @pytest.mark.asyncio
    async def test_query_audit_called(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        with patch(
            "odap.infra.openharness.agui.retrieval_adapter.query_audit"
        ) as mock_audit:
            async for _ in adapter.stream_search(
                "ws1", "test", operator="user1"
            ):
                pass

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["operator"] == "user1"
        assert call_kwargs["query_params"]["retrieval_type"] == "nl"

    @pytest.mark.asyncio
    async def test_query_audit_failure_does_not_break_stream(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        with patch(
            "odap.infra.openharness.agui.retrieval_adapter.query_audit",
            side_effect=RuntimeError("audit failed"),
        ):
            events = []
            async for event in adapter.stream_search("ws1", "test"):
                events.append(event)

        # Stream should still complete normally
        assert events[-1]["type"] == "RUN_FINISHED"

    @pytest.mark.asyncio
    async def test_text_content_chunked(self):
        result = _make_search_result()
        service = _make_mock_service(search_result=result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_search("ws1", "test"):
            events.append(event)

        # Should have multiple TEXT_MESSAGE_CONTENT events (chunked)
        content_events = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert len(content_events) >= 1


# ------------------------------------------------------------------
# RetrievalAGUIAdapter.stream_chain_search
# ------------------------------------------------------------------


class TestStreamChainSearch:
    @pytest.mark.asyncio
    async def test_emits_step_events_for_each_step(self):
        chain_result = {
            "total": 2,
            "reasoning": {
                "steps": [
                    {"action": {"thought": "step1"}, "result": "r1"},
                    {"action": {"thought": "step2"}, "result": "r2"},
                ],
                "cycle_detected": False,
            },
        }
        service = _make_mock_service(chain_result=chain_result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_chain_search("ws1", "test"):
            events.append(event)

        types = [e["type"] for e in events]
        # 2 steps → 2 STEP_STARTED + 2 STEP_FINISHED
        assert types.count("STEP_STARTED") == 2
        assert types.count("STEP_FINISHED") == 2
        assert types[0] == "RUN_STARTED"
        assert types[-1] == "RUN_FINISHED"

    @pytest.mark.asyncio
    async def test_cycle_detection_triggers_interrupt(self):
        chain_result = {
            "total": 1,
            "reasoning": {
                "steps": [{"action": {"thought": "loop"}, "result": "r"}],
                "cycle_detected": True,
            },
        }
        service = _make_mock_service(chain_result=chain_result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_chain_search("ws1", "test"):
            events.append(event)

        run_finished = events[-1]
        assert run_finished["outcome"]["type"] == "interrupt"
        interrupt = run_finished["outcome"]["interrupts"][0]
        assert "循环" in interrupt["message"]

    @pytest.mark.asyncio
    async def test_no_steps_no_text_messages(self):
        chain_result = {
            "total": 0,
            "reasoning": {"steps": [], "cycle_detected": False},
        }
        service = _make_mock_service(chain_result=chain_result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        events = []
        async for event in adapter.stream_chain_search("ws1", "test"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "TEXT_MESSAGE_START" not in types
        assert types[-1] == "RUN_FINISHED"

    @pytest.mark.asyncio
    async def test_chain_query_audit_called(self):
        chain_result = {
            "total": 1,
            "reasoning": {"steps": [{"action": {"thought": "s"}}], "cycle_detected": False},
        }
        service = _make_mock_service(chain_result=chain_result)
        adapter = RetrievalAGUIAdapter(retrieval_service=service)

        with patch(
            "odap.infra.openharness.agui.retrieval_adapter.query_audit"
        ) as mock_audit:
            async for _ in adapter.stream_chain_search("ws1", "test", operator="u1"):
                pass

        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["query_params"]["retrieval_type"] == "chain"


# ------------------------------------------------------------------
# RetrievalAGUIAdapter helpers
# ------------------------------------------------------------------


class TestAdapterHelpers:
    def test_check_confidence_no_confidence_field(self):
        """Rows without confidence field should not trigger Interrupt."""
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        result = SearchResult(
            query="t", mode="nl", total=1,
            rows=[{"id": "e1", "name": "E1"}],  # no confidence field
        )
        interrupt = adapter._check_confidence(result)
        assert interrupt is None

    @pytest.mark.asyncio
    async def test_check_confidence_mixed(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        result = SearchResult(
            query="t", mode="nl", total=3,
            rows=[
                {"id": "e1", "confidence": 0.9},
                {"id": "e2", "confidence": 0.3},  # low
                {"id": "e3", "confidence": 0.7},
            ],
        )
        interrupt = adapter._check_confidence(result)
        assert interrupt is not None
        assert interrupt.metadata["low_confidence_count"] == 1

    def test_chunk_text_splits_correctly(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        chunks = adapter._chunk_text("abcdefghij", 3)
        assert chunks == ["abc", "def", "ghi", "j"]

    def test_chunk_text_empty(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        chunks = adapter._chunk_text("", 100)
        assert chunks == [""]

    def test_format_search_result_includes_mode_and_count(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        result = SearchResult(query="t", mode="graph", total=5, rows=[])
        text = adapter._format_search_result(result)
        assert "graph" in text
        assert "5" in text

    def test_format_step_includes_step_number(self):
        adapter = RetrievalAGUIAdapter(retrieval_service=MagicMock())
        text = adapter._format_step({"action": "do something"}, 3)
        assert "步骤 3" in text
        assert "do something" in text


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------


class TestSingleton:
    def test_get_retrieval_agui_adapter_returns_instance(self):
        adapter = get_retrieval_agui_adapter()
        assert isinstance(adapter, RetrievalAGUIAdapter)

    def test_default_confidence_threshold(self):
        assert CONFIDENCE_THRESHOLD == 0.5


# ------------------------------------------------------------------
# Routes query_audit 埋点
# ------------------------------------------------------------------


class TestRoutesQueryAudit:
    """验证检索路由的 query_audit 埋点（Iter 3.2 #5）。"""

    @pytest.mark.asyncio
    async def test_unified_query_calls_query_audit(self):
        from odap.biz.core.ontology.semantic_retrieval.api.routes import router
        from odap.infra.security.audit_helper import query_audit

        # Mock the service
        mock_result = SearchResult(query="t", mode="nl", total=1, rows=[])
        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service"
        ) as mock_svc, patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes.query_audit"
        ) as mock_audit:
            mock_svc.search = AsyncMock(return_value=mock_result)
            # Find the unified_query endpoint and call it
            from odap.biz.core.ontology.semantic_retrieval.api.routes import unified_query
            from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

            request = SearchRequest(query="test", mode="auto")
            user = {"sub": "user1", "name": "Test", "ws_id": "ws1"}
            await unified_query(request, user)

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["operator"] == "user1"
        assert call_kwargs["workspace_id"] == "ws1"

    @pytest.mark.asyncio
    async def test_graph_search_calls_query_audit(self):
        from odap.biz.core.ontology.semantic_retrieval.api.routes import graph_search
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service"
        ) as mock_svc, patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes.query_audit"
        ) as mock_audit:
            mock_svc.graph_search = AsyncMock(
                return_value={"total": 2, "rows": [], "explain": None}
            )
            request = SearchRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            await graph_search(request, user)

        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["query_params"]["retrieval_type"] == "graph"

    @pytest.mark.asyncio
    async def test_nl_search_calls_query_audit(self):
        from odap.biz.core.ontology.semantic_retrieval.api.routes import nl_search
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service"
        ) as mock_svc, patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes.query_audit"
        ) as mock_audit:
            mock_svc.nl_search = AsyncMock(
                return_value={"total": 1, "rows": [], "explain": None}
            )
            request = SearchRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            await nl_search(request, user)

        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["query_params"]["retrieval_type"] == "nl"

    @pytest.mark.asyncio
    async def test_query_audit_failure_does_not_break_request(self):
        """query_audit 失败不应影响检索响应。"""
        from odap.biz.core.ontology.semantic_retrieval.api.routes import unified_query
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

        mock_result = SearchResult(query="t", mode="nl", total=1, rows=[])
        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service"
        ) as mock_svc, patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes.query_audit",
            side_effect=RuntimeError("audit failed"),
        ):
            mock_svc.search = AsyncMock(return_value=mock_result)
            request = SearchRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            result = await unified_query(request, user)

        # Request should still succeed
        assert result.total == 1


# ------------------------------------------------------------------
# SSE streaming endpoints
# ------------------------------------------------------------------


class TestSSEStreamEndpoints:
    @pytest.mark.asyncio
    async def test_stream_query_returns_streaming_response(self):
        from fastapi.responses import StreamingResponse

        from odap.biz.core.ontology.semantic_retrieval.api.routes import stream_query
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

        mock_result = SearchResult(query="t", mode="nl", total=1, rows=[])
        mock_service = MagicMock()
        mock_service.search = AsyncMock(return_value=mock_result)

        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service",
            mock_service,
        ):
            request = SearchRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            response = await stream_query(request, user)

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_chain_query_returns_streaming_response(self):
        from fastapi.responses import StreamingResponse

        from odap.biz.core.ontology.semantic_retrieval.api.routes import stream_chain_query
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import ChainRequest

        mock_chain_result = {
            "total": 1,
            "reasoning": {"steps": [], "cycle_detected": False},
        }
        mock_service = MagicMock()
        mock_service.chain_search = AsyncMock(return_value=mock_chain_result)

        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service",
            mock_service,
        ):
            request = ChainRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            response = await stream_chain_query(request, user)

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_query_emits_valid_sse_data(self):
        """验证 SSE 流式端点输出格式正确（data: JSON\n\n）。"""
        from odap.biz.core.ontology.semantic_retrieval.api.routes import stream_query
        from odap.biz.core.ontology.semantic_retrieval.models.schemas import SearchRequest

        mock_result = SearchResult(query="t", mode="nl", total=1, rows=[])
        mock_service = MagicMock()
        mock_service.search = AsyncMock(return_value=mock_result)

        with patch(
            "odap.biz.core.ontology.semantic_retrieval.api.routes._service",
            mock_service,
        ):
            request = SearchRequest(query="test")
            user = {"sub": "u1", "ws_id": "ws1"}
            response = await stream_query(request, user)

        # Consume the SSE generator
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        assert len(chunks) > 0
        # Each chunk should be SSE format: "data: {...}\n\n"
        for chunk in chunks:
            text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")
            assert text.startswith("data: ")
            assert text.endswith("\n\n")
            # Extract JSON and verify it's valid
            json_str = text[6:-2]
            data = json.loads(json_str)
            assert "type" in data
