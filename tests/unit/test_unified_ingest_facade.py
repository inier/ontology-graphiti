"""test_unified_ingest_facade.py - UnifiedIngestFacade 单元测试

测试统一摄入门面的单例模式、源类型路由、摄入方法和错误处理。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# 延迟导入 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def facade():
    """创建 UnifiedIngestFacade 实例（重置单例）"""
    try:
        from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade
    except ImportError:
        pytest.skip("UnifiedIngestFacade not importable")
    # 重置单例
    UnifiedIngestFacade._instance = None
    instance = UnifiedIngestFacade()
    # 重置模块级单例
    import odap.biz.data.ingest.unified_ingest_facade as mod
    mod._facade_instance = None
    return instance


# ---------------------------------------------------------------------------
# TestSingleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_instance_returns_same_object(self):
        try:
            from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade
        except ImportError:
            pytest.skip("UnifiedIngestFacade not importable")
        UnifiedIngestFacade._instance = None
        a = UnifiedIngestFacade.get_instance()
        b = UnifiedIngestFacade.get_instance()
        assert a is b

    def test_get_instance_creates_instance(self):
        try:
            from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade
        except ImportError:
            pytest.skip("UnifiedIngestFacade not importable")
        UnifiedIngestFacade._instance = None
        instance = UnifiedIngestFacade.get_instance()
        assert isinstance(instance, UnifiedIngestFacade)


# ---------------------------------------------------------------------------
# TestSourceTypeRouting
# ---------------------------------------------------------------------------

class TestSourceTypeRouting:
    def test_document_driven_source_types(self, facade):
        supported = facade.get_supported_source_types()
        doc_types = supported["document_driven"]
        assert "url" in doc_types
        assert "news" in doc_types
        assert "tavily" in doc_types
        assert "manual" in doc_types
        assert "json" in doc_types
        assert "natural_language" in doc_types
        assert "random_events" in doc_types
        assert "database" in doc_types

    def test_event_driven_source_types(self, facade):
        supported = facade.get_supported_source_types()
        event_types = supported["event_driven"]
        assert "webhook" in event_types
        assert "sensor" in event_types
        assert "mcp" in event_types
        assert "file" in event_types
        assert "api" in event_types

    def test_get_supported_source_types_returns_dict(self, facade):
        result = facade.get_supported_source_types()
        assert isinstance(result, dict)
        assert "document_driven" in result
        assert "event_driven" in result


# ---------------------------------------------------------------------------
# TestIngest
# ---------------------------------------------------------------------------

class TestIngest:
    @pytest.mark.asyncio
    async def test_ingest_unknown_source_type(self, facade):
        result = await facade.ingest("unknown_type")
        assert result["status"] == "error"
        assert "Unknown source type" in result["message"]

    @pytest.mark.asyncio
    async def test_ingest_url_routes_to_document(self, facade):
        mock_service = AsyncMock()
        mock_service.ingest_from_url = AsyncMock(return_value="rec-001")
        facade._ingest_service = mock_service

        result = await facade.ingest("url", url="https://example.com")
        assert result["status"] == "ok"
        assert result["source_type"] == "url"
        assert result["routed_to"] == "IngestService"
        assert result["record_id"] == "rec-001"

    @pytest.mark.asyncio
    async def test_ingest_news_routes_to_document(self, facade):
        mock_service = AsyncMock()
        mock_service.ingest_from_news = AsyncMock(return_value="rec-002")
        facade._ingest_service = mock_service

        result = await facade.ingest("news", query="test query")
        assert result["status"] == "ok"
        assert result["routed_to"] == "IngestService"

    @pytest.mark.asyncio
    async def test_ingest_manual_routes_to_document(self, facade):
        mock_service = AsyncMock()
        mock_service.ingest_from_manual = AsyncMock(return_value="rec-003")
        facade._ingest_service = mock_service

        result = await facade.ingest("manual", form_data="some data")
        assert result["status"] == "ok"
        assert result["routed_to"] == "IngestService"

    @pytest.mark.asyncio
    async def test_ingest_webhook_routes_to_event(self, facade):
        mock_hub = AsyncMock()
        # Mock the process_event to return an object with event_id and extraction
        mock_output = MagicMock()
        mock_output.event_id = "evt-001"
        mock_output.extraction.confidence = 0.9
        mock_hub.process_event = AsyncMock(return_value=mock_output)
        mock_hub.ingest_webhook = MagicMock(return_value="evt-001")
        facade._perception_hub = mock_hub

        result = await facade.ingest("webhook", payload={"key": "value"})
        assert result["status"] == "ok"
        assert result["routed_to"] == "PerceptionHub"

    @pytest.mark.asyncio
    async def test_ingest_sensor_routes_to_event(self, facade):
        mock_hub = AsyncMock()
        mock_hub.ingest_sensor = MagicMock(return_value=None)
        facade._perception_hub = mock_hub

        result = await facade.ingest("sensor", sensor_id="s1", value=42.0)
        assert result["status"] == "ok"
        assert result["routed_to"] == "PerceptionHub"
        assert "Sensor reading queued" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_ingest_document_error_handling(self, facade):
        mock_service = AsyncMock()
        mock_service.ingest_from_url = AsyncMock(side_effect=RuntimeError("connection failed"))
        facade._ingest_service = mock_service

        result = await facade.ingest("url", url="https://example.com")
        assert result["status"] == "error"
        assert "connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_ingest_json_routes_to_document(self, facade):
        mock_service = AsyncMock()
        mock_service.ingest_from_json = AsyncMock(return_value="rec-json-001")
        facade._ingest_service = mock_service

        result = await facade.ingest("json", raw_json='{"key": "value"}')
        assert result["status"] == "ok"
        assert result["source_type"] == "json"
