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


class TestEventIngestExtractionPassthrough:
    """规则 14：门面必须把 PerceptionHub 的抽取结果透传上来，且不得无视 FAILED。

    用真实 PerceptionOutput / ExtractionResult（非 MagicMock）驱动，确保
    `output.status == PerceptionStatus.FAILED` 判定与 `extraction.model_dump()`
    走真实对象路径（规则 14 要求 6：测试执行真实函数体）。
    """

    @pytest.mark.asyncio
    async def test_ingest_event_returns_extraction_payload(self, facade):
        from odap.biz.data.perception.schemas import (
            PerceptionOutput, PerceptionStatus, ExtractionResult,
        )

        real_output = PerceptionOutput(
            event_id="evt-001",
            extraction=ExtractionResult(
                entities=[{"entity_id": "e1", "entity_type": "Unit", "name": "红方装甲营"}],
                relations=[{"relation_id": "r1", "relation_type": "隶属于",
                            "source_entity": "红方装甲营", "target_entity": "红方第1师"}],
                events=[{"event_id": "ev1", "event_type": "装甲推进"}],
                actions=[],
                confidence=0.8,
            ),
            status=PerceptionStatus.STORED,
        )
        mock_hub = AsyncMock()
        mock_hub.process_event = AsyncMock(return_value=real_output)
        mock_hub.ingest_webhook = MagicMock(return_value="evt-001")
        facade._perception_hub = mock_hub

        result = await facade.ingest("webhook", payload={"key": "value"})

        assert result["status"] == "ok", result
        assert result["routed_to"] == "PerceptionHub"
        ext = result["extraction"]
        assert ext["confidence"] == 0.8
        assert ext["entities"][0]["name"] == "红方装甲营"
        assert ext["relations"][0]["relation_type"] == "隶属于"
        assert ext["events"][0]["event_type"] == "装甲推进"
        assert ext["actions"] == []

    @pytest.mark.asyncio
    async def test_ingest_event_propagates_failed_status(self, facade):
        from odap.biz.data.perception.schemas import (
            PerceptionOutput, PerceptionStatus, ExtractionResult,
        )

        failed = PerceptionOutput(
            event_id="evt-002",
            extraction=ExtractionResult(),
            status=PerceptionStatus.FAILED,
            error="LLM 抽取超时",
        )
        mock_hub = AsyncMock()
        mock_hub.process_event = AsyncMock(return_value=failed)
        mock_hub.ingest_webhook = MagicMock(return_value="evt-002")
        facade._perception_hub = mock_hub

        result = await facade.ingest("webhook", payload={"key": "value"})

        assert result["status"] == "error", result
        assert "LLM 抽取超时" in result["message"]
        assert result["event_id"] == "evt-002"
