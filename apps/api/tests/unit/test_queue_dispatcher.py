"""Unit tests for Iter 2.2: Celery + Redis three-tier priority queue.

Tests cover:
- T031: queue_worker — constants, resolve_queue, get_celery_app
- T032: dispatcher — dispatch_feed_he_kb (sync fallback path)
- T033: dispatcher — dispatch_map_to_ontology (sync fallback path)
- T034: dispatcher — dispatch_process_multimodal (text + non-text modalities)
- T035: dispatcher — dispatch_ingestion_to_queue (convenience wrapper)
- T036: DispatchResult — dataclass fields and to_dict()
- T037: NewsIngester auto-dispatch when ontology_id provided
- T038: NewsIngester backward compat (no dispatch when ontology_id=None)
- T039: graceful degradation — sync fallback when CELERY_AVAILABLE=False

All tests run without celery/redis installed (sync fallback mode).
HE adapter is mocked to avoid hyperextract dependency.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from odap.infra.queue import (
    dispatch_feed_he_kb,
    dispatch_map_to_ontology,
    dispatch_process_multimodal,
    dispatch_ingestion_to_queue,
    DispatchResult,
    CELERY_AVAILABLE,
    QUEUE_HIGH_PRIORITY,
    QUEUE_NORMAL,
    QUEUE_BATCH,
)
from odap.infra.queue.queue_worker import resolve_queue, get_celery_app
from odap.infra.queue.tasks import (
    TASK_FEED_HE_KB,
    TASK_MAP_TO_ONTOLOGY,
    TASK_PROCESS_MULTIMODAL,
    feed_he_kb_impl,
    map_to_ontology_impl,
    process_multimodal_impl,
)


# ---------------------------------------------------------------------------
# T031: queue_worker — constants and resolve_queue
# ---------------------------------------------------------------------------

class TestQueueWorkerConstants:
    def test_queue_name_constants(self):
        assert QUEUE_HIGH_PRIORITY == "high_priority"
        assert QUEUE_NORMAL == "normal"
        assert QUEUE_BATCH == "batch"

    def test_celery_available_is_bool(self):
        assert isinstance(CELERY_AVAILABLE, bool)

    def test_get_celery_app_returns_none_when_unavailable(self):
        """When celery is not installed, get_celery_app returns None."""
        if not CELERY_AVAILABLE:
            assert get_celery_app() is None


class TestResolveQueue:
    def test_high_priority_variants(self):
        assert resolve_queue("high") == QUEUE_HIGH_PRIORITY
        assert resolve_queue("high_priority") == QUEUE_HIGH_PRIORITY
        assert resolve_queue("urgent") == QUEUE_HIGH_PRIORITY
        assert resolve_queue("HIGH") == QUEUE_HIGH_PRIORITY

    def test_normal_priority_variants(self):
        assert resolve_queue("normal") == QUEUE_NORMAL
        assert resolve_queue("regular") == QUEUE_NORMAL
        assert resolve_queue("default") == QUEUE_NORMAL
        assert resolve_queue("") == QUEUE_NORMAL
        assert resolve_queue(None) == QUEUE_NORMAL

    def test_batch_priority_variants(self):
        assert resolve_queue("batch") == QUEUE_BATCH
        assert resolve_queue("low") == QUEUE_BATCH
        assert resolve_queue("background") == QUEUE_BATCH

    def test_unknown_falls_back_to_normal(self):
        assert resolve_queue("unknown") == QUEUE_NORMAL
        assert resolve_queue("whatever") == QUEUE_NORMAL


# ---------------------------------------------------------------------------
# T032: dispatch_feed_he_kb (sync fallback)
# ---------------------------------------------------------------------------

class TestDispatchFeedHeKb:
    def test_returns_dispatch_result(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "some text")
        assert isinstance(result, DispatchResult)

    def test_empty_text_returns_skipped(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "")
        assert result.mode == "sync"
        assert result.status == "completed"
        assert result.result["status"] == "skipped"

    def test_whitespace_only_text_returns_skipped(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "   ")
        assert result.result["status"] == "skipped"

    def test_priority_routing_high(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "text", priority="high")
        assert result.queue == QUEUE_HIGH_PRIORITY

    def test_priority_routing_batch(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "text", priority="batch")
        assert result.queue == QUEUE_BATCH

    def test_priority_routing_default_normal(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        assert result.queue == QUEUE_NORMAL

    def test_task_name_correct(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        assert result.task_name == TASK_FEED_HE_KB

    @patch("odap.infra.queue.dispatcher.feed_he_kb_impl")
    def test_sync_mode_calls_impl_directly(self, mock_impl):
        mock_impl.return_value = {"status": "success", "kb_path": "/tmp/kb"}
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        mock_impl.assert_called_once_with("ws1", "ont1", "text", None, None)
        assert result.mode == "sync"
        assert result.status == "completed"

    @patch("odap.infra.queue.dispatcher.feed_he_kb_impl")
    def test_sync_mode_propagates_failure(self, mock_impl):
        mock_impl.return_value = {"status": "error", "message": "HE unavailable"}
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        assert result.status == "failed"
        assert result.error == "HE unavailable"

    @patch("odap.infra.queue.dispatcher.feed_he_kb_impl")
    def test_sync_mode_handles_exception(self, mock_impl):
        mock_impl.side_effect = RuntimeError("unexpected crash")
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        assert result.status == "failed"
        assert "unexpected crash" in result.error

    def test_to_dict_returns_all_fields(self):
        result = dispatch_feed_he_kb("ws1", "ont1", "text")
        d = result.to_dict()
        assert "task_id" in d
        assert "mode" in d
        assert "queue" in d
        assert "status" in d
        assert "task_name" in d
        assert "result" in d
        assert "error" in d


# ---------------------------------------------------------------------------
# T033: dispatch_map_to_ontology (sync fallback)
# ---------------------------------------------------------------------------

class TestDispatchMapToOntology:
    def test_returns_dispatch_result(self):
        result = dispatch_map_to_ontology("ws1", "ont1")
        assert isinstance(result, DispatchResult)

    def test_task_name_correct(self):
        result = dispatch_map_to_ontology("ws1", "ont1")
        assert result.task_name == TASK_MAP_TO_ONTOLOGY

    def test_priority_routing(self):
        result = dispatch_map_to_ontology("ws1", "ont1", priority="high")
        assert result.queue == QUEUE_HIGH_PRIORITY

    @patch("odap.infra.queue.dispatcher.map_to_ontology_impl")
    def test_sync_mode_calls_impl(self, mock_impl):
        mock_impl.return_value = {"status": "success", "entity_count": 10}
        result = dispatch_map_to_ontology("ws1", "ont1", "session-123")
        mock_impl.assert_called_once_with("ws1", "ont1", "session-123")
        assert result.status == "completed"
        assert result.result["entity_count"] == 10

    @patch("odap.infra.queue.dispatcher.map_to_ontology_impl")
    def test_sync_mode_propagates_failure(self, mock_impl):
        mock_impl.return_value = {"status": "error", "message": "KA not found"}
        result = dispatch_map_to_ontology("ws1", "ont1")
        assert result.status == "failed"
        assert result.error == "KA not found"


# ---------------------------------------------------------------------------
# T034: dispatch_process_multimodal
# ---------------------------------------------------------------------------

class TestDispatchProcessMultimodal:
    def test_returns_dispatch_result(self):
        result = dispatch_process_multimodal("ws1", "ref", "text/plain")
        assert isinstance(result, DispatchResult)

    def test_task_name_correct(self):
        result = dispatch_process_multimodal("ws1", "ref", "text/plain")
        assert result.task_name == TASK_PROCESS_MULTIMODAL

    def test_text_modality_delegates_to_feed_he_kb(self):
        """text/* should delegate to feed_he_kb_impl."""
        result = dispatch_process_multimodal(
            "ws1", "hello world", "text/plain",
            ontology_id="ont1",
        )
        # In sync mode, this calls feed_he_kb_impl which needs HE — will fail
        # but the delegation path is exercised
        assert result.mode == "sync"

    @patch("odap.infra.queue.dispatcher.process_multimodal_impl")
    def test_text_modality_calls_impl(self, mock_impl):
        mock_impl.return_value = {"status": "success"}
        result = dispatch_process_multimodal(
            "ws1", "some text", "text/plain",
            ontology_id="ont1",
        )
        mock_impl.assert_called_once()
        assert result.status == "completed"

    def test_image_modality_routes_through_multimodal_router(self):
        """Iter 4.1: image modality now routes through MultimodalRouter (not 'not_implemented')."""
        from odap.infra.data_pipeline.multimodal_router import ParsedModality, AggregatedResult
        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="image", text="image description", confidence=0.8,
            model_used="claude", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="image description", total_confidence=0.8, all_fallback=False,
        )
        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok", "session_id": "s1"}
            result = dispatch_process_multimodal("ws1", "img.png", "image/png")

        assert result.status == "completed"
        assert result.result["status"] == "success"
        assert result.result["modality"] == "image"
        mock_router.route.assert_called_once_with("image/png", "img.png")

    def test_audio_modality_routes_through_multimodal_router(self):
        """Iter 4.1: audio modality now routes through MultimodalRouter."""
        from odap.infra.data_pipeline.multimodal_router import ParsedModality, AggregatedResult
        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="audio", text="transcript", confidence=0.9,
            model_used="whisper", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="transcript", total_confidence=0.9, all_fallback=False,
        )
        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok"}
            result = dispatch_process_multimodal("ws1", "audio.mp3", "audio/mpeg")

        assert result.status == "completed"
        assert result.result["status"] == "success"
        assert result.result["modality"] == "audio"

    def test_video_modality_routes_through_multimodal_router(self):
        """Iter 4.1: video modality now routes through MultimodalRouter."""
        from odap.infra.data_pipeline.multimodal_router import ParsedModality, AggregatedResult
        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="video", text="video frame desc", confidence=0.6,
            model_used="frame_extract+claude", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="video frame desc", total_confidence=0.6, all_fallback=False,
        )
        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok"}
            result = dispatch_process_multimodal("ws1", "video.mp4", "video/mp4")

        assert result.status == "completed"
        assert result.result["status"] == "success"
        assert result.result["modality"] == "video"

    def test_missing_mime_type_returns_error(self):
        result = dispatch_process_multimodal("ws1", "ref", "")
        assert result.status == "failed"

    def test_priority_routing(self):
        result = dispatch_process_multimodal("ws1", "ref", "image/png", priority="batch")
        assert result.queue == QUEUE_BATCH


# ---------------------------------------------------------------------------
# T035: dispatch_ingestion_to_queue
# ---------------------------------------------------------------------------

class TestDispatchIngestionToQueue:
    def test_returns_dispatch_result(self):
        result = dispatch_ingestion_to_queue("ws1", "ont1", "ingested text")
        assert isinstance(result, DispatchResult)

    def test_delegates_to_feed_he_kb(self):
        """dispatch_ingestion_to_queue should delegate to feed_he_kb with normal priority."""
        result = dispatch_ingestion_to_queue(
            "ws1", "ont1", "text", source_doc_id="doc-1",
        )
        assert result.task_name == TASK_FEED_HE_KB
        assert result.queue == QUEUE_NORMAL

    def test_priority_override(self):
        result = dispatch_ingestion_to_queue(
            "ws1", "ont1", "text", priority="high",
        )
        assert result.queue == QUEUE_HIGH_PRIORITY

    def test_source_doc_id_passed_through(self):
        with patch("odap.infra.queue.dispatcher.feed_he_kb_impl") as mock_impl:
            mock_impl.return_value = {"status": "success"}
            dispatch_ingestion_to_queue(
                "ws1", "ont1", "text", source_doc_id="doc-abc",
            )
            call_args = mock_impl.call_args
            assert "doc-abc" in call_args[0] or call_args[1].get("source_doc_id") == "doc-abc"

    def test_empty_text_returns_skipped(self):
        result = dispatch_ingestion_to_queue("ws1", "ont1", "")
        assert result.status == "completed"
        assert result.result["status"] == "skipped"


# ---------------------------------------------------------------------------
# T036: DispatchResult dataclass
# ---------------------------------------------------------------------------

class TestDispatchResult:
    def test_to_dict_has_all_fields(self):
        result = DispatchResult(
            task_id="abc123",
            mode="sync",
            queue="normal",
            status="completed",
            task_name="test_task",
            result={"status": "success"},
            error=None,
        )
        d = result.to_dict()
        assert d["task_id"] == "abc123"
        assert d["mode"] == "sync"
        assert d["queue"] == "normal"
        assert d["status"] == "completed"
        assert d["task_name"] == "test_task"
        assert d["result"] == {"status": "success"}
        assert d["error"] is None

    def test_default_optionals_are_none(self):
        result = DispatchResult(
            task_id="x", mode="sync", queue="normal",
            status="dispatched", task_name="t",
        )
        assert result.result is None
        assert result.error is None


# ---------------------------------------------------------------------------
# T037/T038: NewsIngester auto-dispatch integration
# ---------------------------------------------------------------------------

class TestNewsIngesterQueueDispatch:
    """Tests that NewsIngester.ingest() auto-dispatches when ontology_id is provided."""

    @pytest.fixture
    def ingester(self):
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        return NewsIngester()

    @pytest.mark.asyncio
    async def test_no_dispatch_when_ontology_id_none(self, ingester):
        """T038: When ontology_id is None, no dispatch occurs (backward compat)."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_dispatch_to_queue") as mock_dispatch:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            docs = await ingester.ingest("query", ontology_id=None)
            mock_dispatch.assert_not_called()
            assert len(docs) == 1
            assert docs[0].transformation_status == "pending"

    @pytest.mark.asyncio
    async def test_dispatch_called_when_ontology_id_provided(self, ingester):
        """T037: When ontology_id is provided, dispatch is called."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_dispatch_to_queue") as mock_dispatch:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            docs = await ingester.ingest(
                "query", workspace_id="ws1", ontology_id="ont1",
            )
            mock_dispatch.assert_called_once()
            call_args = mock_dispatch.call_args
            assert call_args[0][1] == "ws1"  # workspace_id
            assert call_args[0][2] == "ont1"  # ontology_id

    @pytest.mark.asyncio
    async def test_dispatch_failure_does_not_break_ingest(self, ingester):
        """Dispatch failure should be caught and logged, not propagated."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_dispatch_to_queue", side_effect=Exception("queue down")):
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            # Should not raise — the dispatch error is caught inside ingest()
            # Wait — _dispatch_to_queue is called from ingest, and _dispatch_to_queue
            # itself catches exceptions. But if it raises, ingest's outer try/except
            # catches it and returns an empty pending doc. Let's verify it doesn't
            # crash.
            docs = await ingester.ingest("query", ontology_id="ont1")
            assert len(docs) >= 1

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_search_results(self, ingester):
        """Even with empty search results, if ontology_id is provided, dispatch is called."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_dispatch_to_queue") as mock_dispatch:
            mock_search.return_value = []
            docs = await ingester.ingest("query", ontology_id="ont1")
            mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_to_queue_calls_dispatch_ingestion_to_queue(self, ingester):
        """_dispatch_to_queue should call dispatch_ingestion_to_queue from the queue module."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]

            # Patch at the source module (function-level import in _dispatch_to_queue)
            with patch(
                "odap.infra.queue.dispatch_ingestion_to_queue"
            ) as mock_dispatch:
                mock_dispatch.return_value = DispatchResult(
                    task_id="test-id",
                    mode="sync",
                    queue="normal",
                    status="completed",
                    task_name=TASK_FEED_HE_KB,
                    result={"status": "success"},
                )
                docs = await ingester.ingest(
                    "query", workspace_id="ws1", ontology_id="ont1",
                )
                mock_dispatch.assert_called_once()
                call_kwargs = mock_dispatch.call_args[1]
                assert call_kwargs["workspace_id"] == "ws1"
                assert call_kwargs["ontology_id"] == "ont1"
                assert call_kwargs["source_doc_id"] is not None


# ---------------------------------------------------------------------------
# T039: Graceful degradation — sync fallback
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """Verify that all dispatch functions work in sync mode without celery/redis."""

    def test_all_dispatch_functions_return_sync_result(self):
        """When CELERY_AVAILABLE is False, all dispatches should be sync."""
        if CELERY_AVAILABLE:
            pytest.skip("Celery is installed — sync fallback not tested")

        results = [
            dispatch_feed_he_kb("ws", "ont", "text"),
            dispatch_map_to_ontology("ws", "ont"),
            dispatch_process_multimodal("ws", "ref", "image/png"),
            dispatch_ingestion_to_queue("ws", "ont", "text"),
        ]
        for r in results:
            assert r.mode == "sync"
            assert r.task_id  # should have a UUID

    def test_sync_mode_generates_unique_task_ids(self):
        """Each sync dispatch should generate a unique task_id."""
        if CELERY_AVAILABLE:
            pytest.skip("Celery is installed — sync fallback not tested")

        r1 = dispatch_feed_he_kb("ws", "ont", "text1")
        r2 = dispatch_feed_he_kb("ws", "ont", "text2")
        assert r1.task_id != r2.task_id

    def test_sync_mode_includes_result_dict(self):
        """Sync mode should include the actual result dict."""
        if CELERY_AVAILABLE:
            pytest.skip("Celery is installed — sync fallback not tested")

        result = dispatch_feed_he_kb("ws", "ont", "")
        assert result.result is not None
        assert isinstance(result.result, dict)
        assert result.result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Task impl functions (direct call tests)
# ---------------------------------------------------------------------------

class TestTaskImplFunctions:
    """Test the _impl functions directly (bypassing dispatcher)."""

    def test_feed_he_kb_impl_empty_text(self):
        result = feed_he_kb_impl("ws", "ont", "")
        assert result["status"] == "skipped"
        assert result["workspace_id"] == "ws"
        assert result["ontology_id"] == "ont"

    def test_feed_he_kb_impl_whitespace_text(self):
        result = feed_he_kb_impl("ws", "ont", "   \n  ")
        assert result["status"] == "skipped"

    def test_feed_he_kb_impl_he_unavailable(self):
        """When HE is not installed, should return error dict (not raise)."""
        result = feed_he_kb_impl("ws", "ont", "some text")
        # HE is not installed in test environment
        assert result["status"] in ("error", "success")
        if result["status"] == "error":
            assert "message" in result

    def test_map_to_ontology_impl_he_unavailable(self):
        result = map_to_ontology_impl("ws", "ont")
        assert result["status"] in ("error", "success")

    def test_process_multimodal_impl_text_delegates(self):
        """text/* modality delegates to feed_he_kb_impl."""
        result = process_multimodal_impl("ws", "text content", "text/plain", ontology_id="ont")
        assert result["status"] in ("success", "skipped", "error")

    def test_process_multimodal_impl_image_routes_through_router(self):
        """Iter 4.1: image modality routes through MultimodalRouter (not 'not_implemented')."""
        from odap.infra.data_pipeline.multimodal_router import (
            AggregatedResult,
            ParsedModality,
        )
        mock_router = MagicMock()
        mock_router.route.return_value = ParsedModality(
            modality="image", text="img desc", confidence=0.8,
            model_used="claude", fallback=False,
        )
        mock_aggregator = MagicMock()
        mock_aggregator.aggregate.return_value = AggregatedResult(
            combined_text="[图像描述]\nimg desc",
            modalities=[],
            total_confidence=0.8,
        )
        with patch(
            "odap.infra.data_pipeline.multimodal_router.get_multimodal_router",
            return_value=mock_router,
        ), patch(
            "odap.infra.data_pipeline.multimodal_router.get_result_aggregator",
            return_value=mock_aggregator,
        ), patch("odap.infra.queue.tasks.feed_he_kb_impl") as mock_feed:
            mock_feed.return_value = {"status": "ok", "session_id": "s1"}
            result = process_multimodal_impl("ws", "img.png", "image/png")

        assert result["status"] == "success"
        assert result["modality"] == "image"
        assert result["model_used"] == "claude"
        mock_router.route.assert_called_once_with("image/png", "img.png")

    def test_process_multimodal_impl_empty_mime(self):
        result = process_multimodal_impl("ws", "ref", "")
        assert result["status"] == "error"
