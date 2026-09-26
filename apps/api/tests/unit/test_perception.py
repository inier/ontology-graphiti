import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from odap.biz.data.perception.hub import PerceptionHub
from odap.biz.data.perception.schemas import (
    PerceptionEvent,
    PerceptionOutput,
    ExtractionResult,
    PerceptionSourceType,
    PerceptionStatus,
    PerceptionPriority,
)
from odap.biz.data.perception.observers.base_observers import (
    BaseObserver,
    MCPObserver,
    FileObserver,
    APIObserver,
    SensorObserver,
    NewsObserver,
    WebhookObserver,
)


class TestPerceptionHubInit:
    def test_default_observers_registered(self):
        hub = PerceptionHub()
        expected_names = {
            "mcp_observer",
            "file_observer",
            "api_observer",
            "sensor_observer",
            "news_observer",
            "webhook_observer",
        }
        assert set(hub._observers.keys()) == expected_names

    def test_default_observers_types(self):
        hub = PerceptionHub()
        assert isinstance(hub._observers["mcp_observer"], MCPObserver)
        assert isinstance(hub._observers["file_observer"], FileObserver)
        assert isinstance(hub._observers["api_observer"], APIObserver)
        assert isinstance(hub._observers["sensor_observer"], SensorObserver)
        assert isinstance(hub._observers["news_observer"], NewsObserver)
        assert isinstance(hub._observers["webhook_observer"], WebhookObserver)

    def test_event_buffer_empty_on_init(self):
        hub = PerceptionHub()
        assert hub._event_buffer == []

    def test_lazy_properties_none_on_init(self):
        hub = PerceptionHub()
        assert hub._write_proxy is None
        assert hub._query_service is None
        assert hub._oms is None
        assert hub._pipeline is None


class TestRegisterRemoveObserver:
    def test_register_observer(self):
        hub = PerceptionHub()
        custom_obs = MagicMock(spec=BaseObserver)
        custom_obs.name = "custom_observer"
        hub.register_observer(custom_obs)
        assert "custom_observer" in hub._observers
        assert hub._observers["custom_observer"] is custom_obs

    def test_register_observer_replaces_existing(self):
        hub = PerceptionHub()
        new_mcp = MagicMock(spec=BaseObserver)
        new_mcp.name = "mcp_observer"
        hub.register_observer(new_mcp)
        assert hub._observers["mcp_observer"] is new_mcp

    def test_remove_observer(self):
        hub = PerceptionHub()
        assert "api_observer" in hub._observers
        hub.remove_observer("api_observer")
        assert "api_observer" not in hub._observers

    def test_remove_observer_nonexistent_no_error(self):
        hub = PerceptionHub()
        hub.remove_observer("nonexistent_observer")

    def test_remove_and_re_add_observer(self):
        hub = PerceptionHub()
        hub.remove_observer("sensor_observer")
        assert "sensor_observer" not in hub._observers
        new_sensor = MagicMock(spec=BaseObserver)
        new_sensor.name = "sensor_observer"
        hub.register_observer(new_sensor)
        assert hub._observers["sensor_observer"] is new_sensor


class TestIngestManual:
    def test_creates_event_with_correct_fields(self):
        hub = PerceptionHub()
        event = hub.ingest_manual("test content")
        assert event.source_type == PerceptionSourceType.MANUAL
        assert event.source_name == "manual"
        assert event.raw_content == "test content"
        assert event.metadata == {}
        assert event.event_id.startswith("pe_")
        assert event.timestamp != ""
        assert event.status == PerceptionStatus.RECEIVED

    def test_creates_event_with_custom_source_type(self):
        hub = PerceptionHub()
        event = hub.ingest_manual(
            "sensor data",
            source_type=PerceptionSourceType.SENSOR,
            metadata={"location": "lab"},
        )
        assert event.source_type == PerceptionSourceType.SENSOR
        assert event.raw_content == "sensor data"
        assert event.metadata == {"location": "lab"}

    def test_appends_to_event_buffer(self):
        hub = PerceptionHub()
        hub.ingest_manual("event 1")
        hub.ingest_manual("event 2")
        assert len(hub._event_buffer) == 2
        assert hub._event_buffer[0].raw_content == "event 1"
        assert hub._event_buffer[1].raw_content == "event 2"

    def test_default_metadata_when_none(self):
        hub = PerceptionHub()
        event = hub.ingest_manual("content", metadata=None)
        assert event.metadata == {}


class TestGetStatus:
    def test_returns_observers_info(self):
        hub = PerceptionHub()
        status = hub.get_status()
        assert "observers" in status
        assert "buffer_size" in status
        assert status["buffer_size"] == 0

    def test_observer_info_structure(self):
        hub = PerceptionHub()
        status = hub.get_status()
        for name, info in status["observers"].items():
            assert "type" in info
            assert "enabled" in info
            assert isinstance(info["enabled"], bool)

    def test_buffer_size_tracks_events(self):
        hub = PerceptionHub()
        hub.ingest_manual("a")
        hub.ingest_manual("b")
        status = hub.get_status()
        assert status["buffer_size"] == 2

    def test_reflects_removed_observer(self):
        hub = PerceptionHub()
        hub.remove_observer("api_observer")
        status = hub.get_status()
        assert "api_observer" not in status["observers"]


class TestObserveAll:
    @pytest.mark.asyncio
    async def test_collects_events_from_enabled_observers(self):
        hub = PerceptionHub()
        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "mock_obs"
        mock_obs.enabled = True
        mock_obs.observe = AsyncMock(return_value=[
            PerceptionEvent(
                source_type=PerceptionSourceType.API,
                source_name="mock_obs",
                raw_content="test data",
            )
        ])
        hub._observers = {"mock_obs": mock_obs}

        events = await hub.observe_all()
        assert len(events) == 1
        assert events[0].raw_content == "test data"
        assert events[0].status == PerceptionStatus.RECEIVED

    @pytest.mark.asyncio
    async def test_skips_disabled_observers(self):
        hub = PerceptionHub()
        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "disabled_obs"
        mock_obs.enabled = False
        mock_obs.observe = AsyncMock(return_value=[])
        hub._observers = {"disabled_obs": mock_obs}

        events = await hub.observe_all()
        mock_obs.observe.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigns_event_id_when_missing(self):
        hub = PerceptionHub()
        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "mock_obs"
        mock_obs.enabled = True
        mock_obs.observe = AsyncMock(return_value=[
            PerceptionEvent(
                source_type=PerceptionSourceType.API,
                source_name="mock_obs",
                raw_content="no id event",
                event_id="",
            )
        ])
        hub._observers = {"mock_obs": mock_obs}

        events = await hub.observe_all()
        assert events[0].event_id.startswith("pe_")

    @pytest.mark.asyncio
    async def test_assigns_timestamp_when_missing(self):
        hub = PerceptionHub()
        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "mock_obs"
        mock_obs.enabled = True
        mock_obs.observe = AsyncMock(return_value=[
            PerceptionEvent(
                source_type=PerceptionSourceType.API,
                source_name="mock_obs",
                raw_content="no timestamp",
                timestamp="",
            )
        ])
        hub._observers = {"mock_obs": mock_obs}

        events = await hub.observe_all()
        assert events[0].timestamp != ""

    @pytest.mark.asyncio
    async def test_continues_on_observer_failure(self):
        hub = PerceptionHub()
        failing_obs = MagicMock(spec=BaseObserver)
        failing_obs.name = "failing"
        failing_obs.enabled = True
        failing_obs.observe = AsyncMock(side_effect=RuntimeError("boom"))

        working_obs = MagicMock(spec=BaseObserver)
        working_obs.name = "working"
        working_obs.enabled = True
        working_obs.observe = AsyncMock(return_value=[
            PerceptionEvent(
                source_type=PerceptionSourceType.API,
                source_name="working",
                raw_content="ok",
            )
        ])
        hub._observers = {"failing": failing_obs, "working": working_obs}

        events = await hub.observe_all()
        assert len(events) == 1
        assert events[0].raw_content == "ok"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_observers(self):
        hub = PerceptionHub()
        hub._observers = {}
        events = await hub.observe_all()
        assert events == []


class TestProcessEvent:
    @pytest.mark.asyncio
    async def test_successful_processing_pipeline(self):
        hub = PerceptionHub()
        hub._write_proxy = MagicMock()
        hub._write_proxy.add_episode = AsyncMock(return_value={"status": "success", "name": "test"})
        hub._oms = MagicMock()
        hub._oms.get_object_type = MagicMock(return_value=None)
        hub._oms.create_object_type = MagicMock()

        event = PerceptionEvent(
            event_id="pe_test123",
            source_type=PerceptionSourceType.MANUAL,
            source_name="manual",
            raw_content="test content for extraction",
            timestamp="2025-01-01T00:00:00+00:00",
        )

        extraction = ExtractionResult(
            entities=[{"entity_type": "Person", "name": "Alice"}],
            relations=[],
            events=[],
            actions=[],
            confidence=0.9,
        )

        with patch.object(hub, "_extract", new_callable=AsyncMock, return_value=extraction):
            output = await hub.process_event(event)

        assert output.event_id == "pe_test123"
        assert output.status == PerceptionStatus.STORED
        assert output.extraction.confidence == 0.9
        assert output.oms_registered_types == ["Person"]
        assert output.graphiti_episode_id is not None

    @pytest.mark.asyncio
    async def test_failed_processing_returns_failed_output(self):
        hub = PerceptionHub()
        event = PerceptionEvent(
            event_id="pe_fail",
            source_type=PerceptionSourceType.MANUAL,
            source_name="manual",
            raw_content="bad data",
        )

        with patch.object(hub, "_extract", new_callable=AsyncMock, side_effect=RuntimeError("extraction error")):
            output = await hub.process_event(event)

        assert output.status == PerceptionStatus.FAILED
        assert output.error == "extraction error"
        assert output.extraction.confidence == 0.0

    @pytest.mark.asyncio
    async def test_status_transitions_on_success(self):
        hub = PerceptionHub()
        hub._write_proxy = MagicMock()
        hub._write_proxy.add_episode = AsyncMock(return_value={"status": "success", "name": "test"})
        hub._oms = MagicMock()
        hub._oms.get_object_type = MagicMock(return_value=None)

        event = PerceptionEvent(
            event_id="pe_status_test",
            source_type=PerceptionSourceType.MANUAL,
            raw_content="content",
        )

        extraction = ExtractionResult(confidence=0.5)

        with patch.object(hub, "_extract", new_callable=AsyncMock, return_value=extraction):
            await hub.process_event(event)

        assert event.status == PerceptionStatus.STORED


class TestProcessBatch:
    @pytest.mark.asyncio
    async def test_processes_multiple_events(self):
        hub = PerceptionHub()
        hub._write_proxy = MagicMock()
        hub._write_proxy.add_episode = AsyncMock(return_value={"status": "success", "name": "test"})
        hub._oms = MagicMock()
        hub._oms.get_object_type = MagicMock(return_value=None)

        events = [
            PerceptionEvent(
                event_id=f"pe_batch_{i}",
                source_type=PerceptionSourceType.MANUAL,
                raw_content=f"content {i}",
            )
            for i in range(3)
        ]

        extraction = ExtractionResult(confidence=0.5)

        with patch.object(hub, "_extract", new_callable=AsyncMock, return_value=extraction):
            results = await hub.process_batch(events)

        assert len(results) == 3
        assert all(r.status == PerceptionStatus.STORED for r in results)

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self):
        hub = PerceptionHub()
        results = await hub.process_batch([])
        assert results == []


class TestObserveAndProcess:
    @pytest.mark.asyncio
    async def test_observes_then_processes(self):
        hub = PerceptionHub()
        hub._write_proxy = MagicMock()
        hub._write_proxy.add_episode = AsyncMock(return_value={"status": "success", "name": "test"})
        hub._oms = MagicMock()
        hub._oms.get_object_type = MagicMock(return_value=None)

        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "mock_obs"
        mock_obs.enabled = True
        mock_obs.observe = AsyncMock(return_value=[
            PerceptionEvent(
                source_type=PerceptionSourceType.API,
                source_name="mock_obs",
                raw_content="observed data",
            )
        ])
        hub._observers = {"mock_obs": mock_obs}

        extraction = ExtractionResult(confidence=0.7)

        with patch.object(hub, "_extract", new_callable=AsyncMock, return_value=extraction):
            results = await hub.observe_and_process()

        assert len(results) == 1
        assert results[0].status == PerceptionStatus.STORED

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_events(self):
        hub = PerceptionHub()
        mock_obs = MagicMock(spec=BaseObserver)
        mock_obs.name = "empty_obs"
        mock_obs.enabled = True
        mock_obs.observe = AsyncMock(return_value=[])
        hub._observers = {"empty_obs": mock_obs}

        results = await hub.observe_and_process()
        assert results == []


# ---------------------------------------------------------------------------
# TestOmsProperty — 真实 oms 属性
#
# 此前所有测试都预置 hub._oms = MagicMock()，把属性体整段跳过，因此两个叠加缺陷零覆盖：
#   1. `from odap.biz.core.ontology import OMSStorage` 实测抛 ImportError
#      （__init__._legacy_map 的 OMSStorage 条目映射到模块路径却取不存在的类别名）
#   2. 随后构造的 SQLiteOMSStorage 从未被导入 → NameError
# ---------------------------------------------------------------------------

class TestOmsProperty:
    def test_resolves_to_real_storage(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        hub = PerceptionHub()

        oms = hub.oms

        from odap.biz.core.ontology.public import OMSStorage
        assert isinstance(oms, OMSStorage)
        assert hub.oms is oms  # 第二次访问命中缓存，不重复建库

    def test_real_storage_exposes_methods_map_to_oms_needs(self, tmp_path, monkeypatch):
        """_map_to_oms 依赖 get_object_type / create_object_type，必须是真实可调用方法。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        hub = PerceptionHub()

        assert hub.oms.get_object_type("__no_such_type__") is None
        assert callable(hub.oms.create_object_type)


# ---------------------------------------------------------------------------
# TestExtractRealPath — 真实 _extract 实现
#
# 此前所有测试都 patch.object(hub, "_extract", ...)，函数体从未执行，因此"幻影兜底"
# 存活至今：except 吞掉主路径异常 → 降级到 NewsIngester.extract_ontology（该方法不存在，
# NewsIngester 只有 ingest，且语义是"联网检索"而非"抽取给定文本"）→ 再次被 except 吞掉
# → return ExtractionResult(confidence=0.0)，把"抽取链路坏了"伪装成"这段文本没有内容"。
# ---------------------------------------------------------------------------

class TestExtractRealPath:
    @pytest.fixture(autouse=True)
    def _isolate_data_dir(self, tmp_path, monkeypatch):
        """真实 PipelineContext 的 _storage 默认工厂会建 SQLite 文件。

        不隔离就会写到 pytest 的 CWD（仓库根）下，违反规则 13。
        """
        monkeypatch.setenv("DATA_DIR", str(tmp_path))

    @staticmethod
    def _event(text: str = "刘备在荆州集结兵力"):
        return PerceptionEvent(
            event_id="pe_extract",
            source_type=PerceptionSourceType.MANUAL,
            source_name="manual",
            raw_content=text,
        )

    @staticmethod
    def _patch_handler(mock_handler):
        return patch(
            "odap.biz.core.ontology.public.LLMExtractionStageHandler",
            return_value=mock_handler,
        )

    @pytest.mark.asyncio
    async def test_empty_content_short_circuits_without_llm(self):
        hub = PerceptionHub()

        result = await hub._extract(self._event(""))

        assert result.entities == []
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_returns_handler_output(self):
        hub = PerceptionHub()
        handler = MagicMock()
        handler._extract_with_llm = AsyncMock(return_value=(
            [{"entity_type": "Person", "name": "刘备"}],
            [{"source": "刘备", "target": "荆州", "relation": "位于"}],
            [{"event_type": "集结"}],
        ))

        with self._patch_handler(handler):
            result = await hub._extract(self._event())

        assert result.entities == [{"entity_type": "Person", "name": "刘备"}]
        assert len(result.relations) == 1
        assert len(result.events) == 1
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_context_carries_event_identity(self):
        """context 必须由事件自身字段接线，而不是必填参数缺失或凭命名反推。"""
        hub = PerceptionHub()
        handler = MagicMock()
        handler._extract_with_llm = AsyncMock(return_value=([], [], []))
        event = PerceptionEvent(
            event_id="pe_ctx_1",
            source_type=PerceptionSourceType.NEWS,
            source_name="crawler",
            raw_content="一些文本",
            workspace_id="ws-9",
            scenario_id="sc-9",
        )

        with self._patch_handler(handler):
            await hub._extract(event)

        context = handler._extract_with_llm.call_args[0][1]
        assert context.ingest_id == "pe_ctx_1"
        assert context.scenario_id == "sc-9"
        assert context.workspace_id == "ws-9"
        assert context.source == "news"
        assert context.original_content == "一些文本"

    @pytest.mark.asyncio
    async def test_handler_failure_propagates_not_swallowed(self):
        """规则 14：抽取失败必须显式抛出，不得降级成空结果。"""
        hub = PerceptionHub()
        handler = MagicMock()
        handler._extract_with_llm = AsyncMock(side_effect=RuntimeError("LLM 不可用"))

        with self._patch_handler(handler):
            with pytest.raises(RuntimeError, match="LLM 不可用"):
                await hub._extract(self._event())

    @pytest.mark.asyncio
    async def test_import_error_propagates_not_swallowed(self):
        """原实现有专门的 `except ImportError` 分支，现已移除。"""
        hub = PerceptionHub()

        with patch(
            "odap.biz.core.ontology.public.LLMExtractionStageHandler",
            side_effect=ImportError("no such handler"),
        ):
            with pytest.raises(ImportError, match="no such handler"):
                await hub._extract(self._event())

    def test_phantom_fallback_target_does_not_exist(self):
        """守卫：被删掉的兜底所依赖的方法确实不存在，防止有人"恢复"它。"""
        from odap.biz.core.ontology.public import NewsIngester

        assert not hasattr(NewsIngester, "extract_ontology")
        assert hasattr(NewsIngester, "ingest")

    @pytest.mark.asyncio
    async def test_process_event_marks_failed_on_extract_error(self):
        """端到端：抽取抛错 → FAILED + error 透传，而非 STORED + 空结果。"""
        hub = PerceptionHub()
        handler = MagicMock()
        handler._extract_with_llm = AsyncMock(side_effect=RuntimeError("LLM 不可用"))

        with self._patch_handler(handler):
            output = await hub.process_event(self._event())

        assert output.status == PerceptionStatus.FAILED
        assert "LLM 不可用" in output.error
        assert output.extraction.entities == []
        assert output.graphiti_episode_id is None
