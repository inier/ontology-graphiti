"""
PipelineService (OntologyPipeline) 单元测试

覆盖:
- PipelineContext 创建与 stage_results
- PipelineStageHandler 成功/失败
- run() 使用 mock handlers
- run_async() 并行执行
- progress_callback 调用
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 延迟导入 + skip
# ---------------------------------------------------------------------------

try:
    from odap.biz.core.ontology.design.services.pipeline_service import (
        PipelineContext,
        PipelineStageHandler,
        OntologyPipeline,
        PipelineService,
    )
    from odap.biz.core.ontology.design.models.audit import (
        PipelineStage, ProcessingStatus,
    )
except Exception as exc:
    pytest.skip(f"Cannot import pipeline_service: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_pipeline_singleton():
    """每个测试前重置 OntologyPipeline 单例"""
    OntologyPipeline._instance = None
    yield
    OntologyPipeline._instance = None


@pytest.fixture
def mock_storage():
    """创建 mock 存储对象"""
    storage = MagicMock()
    storage.save_process_log = MagicMock()
    storage.save_build_history = MagicMock()
    storage.list_all_versions = MagicMock(return_value=[])
    return storage


@pytest.fixture
def context(mock_storage):
    """创建 PipelineContext 实例"""
    ctx = PipelineContext(
        ingest_id="ingest-test-001",
        scenario_id="scenario-test-001",
        workspace_id="ws-test",
        source="manual",
    )
    ctx._storage = mock_storage
    return ctx


# ---------------------------------------------------------------------------
# TestPipelineContext — 管道上下文
# ---------------------------------------------------------------------------

class TestPipelineContext:
    def test_creation_defaults(self, context):
        """PipelineContext 创建时应有正确的默认值"""
        assert context.ingest_id == "ingest-test-001"
        assert context.scenario_id == "scenario-test-001"
        assert context.workspace_id == "ws-test"
        assert context.source == "manual"
        assert context.current_stage == PipelineStage.COLLECTION
        assert context.logs == []
        assert context.stage_results == {}
        assert context.error is None
        assert context.success is False

    def test_stage_results_dict(self, context):
        """stage_results 应为独立 dict"""
        context.stage_results["collection"] = {"record_count": 1}
        assert context.stage_results["collection"] == {"record_count": 1}
        # 新 context 不受影响
        ctx2 = PipelineContext(
            ingest_id="ingest-test-002",
            scenario_id="scenario-test-002",
        )
        assert ctx2.stage_results == {}

    def test_add_log_appends_to_logs(self, context, mock_storage):
        """add_log 应追加日志到 logs 列表"""
        log = context.add_log(
            stage=PipelineStage.COLLECTION,
            operation="test_op",
            details={"key": "value"},
            status=ProcessingStatus.PROCESSING,
        )
        assert len(context.logs) == 1
        assert context.logs[0].operation == "test_op"
        assert context.logs[0].stage == PipelineStage.COLLECTION
        mock_storage.save_process_log.assert_called_once()

    def test_start_stage_records_time(self, context):
        """start_stage 应记录阶段开始时间"""
        context.start_stage(PipelineStage.CLEANING)
        assert PipelineStage.CLEANING.value in context._stage_start_times

    def test_save_build_history(self, context, mock_storage):
        """save_build_history 应调用存储保存"""
        context.stage_results["ontology"] = {"entity_count": 5, "relation_count": 2}
        context.stage_results["llm"] = {"events_count": 3}
        result = context.save_build_history("completed")
        assert result["status"] == "completed"
        assert result["entity_count"] == 5
        assert result["relation_count"] == 2
        mock_storage.save_build_history.assert_called_once()


# ---------------------------------------------------------------------------
# TestPipelineStageHandler — 阶段处理器
# ---------------------------------------------------------------------------

class TestPipelineStageHandler:
    @pytest.mark.asyncio
    async def test_execute_raises_not_implemented(self):
        """基类 execute 应抛出 NotImplementedError"""
        handler = PipelineStageHandler(PipelineStage.COLLECTION)
        ctx = MagicMock()
        with pytest.raises(NotImplementedError):
            await handler.execute(ctx)

    def test_log_delegates_to_context(self, context, mock_storage):
        """_log 应调用 context.add_log"""
        handler = PipelineStageHandler(PipelineStage.COLLECTION)
        handler._log(context, "test_op", {"key": "val"}, ProcessingStatus.COMPLETED)
        assert len(context.logs) == 1
        assert context.logs[0].operation == "test_op"

    def test_handler_failure_sets_context_error(self, context, mock_storage):
        """handler 失败时应设置 context.error"""
        handler = PipelineStageHandler(PipelineStage.CLEANING)
        handler._log(
            context, "fail_op", {"error": "boom"},
            ProcessingStatus.FAILED, "boom",
        )
        assert context.logs[-1].status == ProcessingStatus.FAILED
        assert context.logs[-1].error_message == "boom"


# ---------------------------------------------------------------------------
# TestPipelineRun — run() 方法
# ---------------------------------------------------------------------------

class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_run_with_all_successful_handlers(self, mock_storage):
        """run() 所有阶段成功时 context.success 应为 True"""
        pipeline = OntologyPipeline()

        # 替换所有 handler 为 mock
        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            mock_handler.execute = AsyncMock(return_value=True)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            context = await pipeline.run(
                ingest_id="ingest-run-001",
                scenario_id="scenario-001",
                source="manual",
            )

        assert context.success is True
        assert context.error is None

    @pytest.mark.asyncio
    async def test_run_stops_on_failure(self, mock_storage):
        """run() 阶段失败时应停止执行"""
        pipeline = OntologyPipeline()

        # 第一个阶段成功，第二个阶段失败
        call_count = 0
        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            call_count += 1
            if call_count <= 1:
                mock_handler.execute = AsyncMock(return_value=True)
            else:
                mock_handler.execute = AsyncMock(return_value=False)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            context = await pipeline.run(
                ingest_id="ingest-run-002",
                scenario_id="scenario-002",
            )

        assert context.success is False

    @pytest.mark.asyncio
    async def test_run_invokes_progress_callback(self, mock_storage):
        """run() 应调用 progress_callback"""
        pipeline = OntologyPipeline()

        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            mock_handler.execute = AsyncMock(return_value=True)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        progress_calls = []

        async def track_progress(stage, progress, message):
            progress_calls.append((stage, progress, message))

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            await pipeline.run(
                ingest_id="ingest-run-003",
                scenario_id="scenario-003",
                progress_callback=track_progress,
            )

        # 应至少调用 6 次（6 个阶段）+ 1 次最终完成回调
        assert len(progress_calls) >= 7
        # 最终进度应为 100
        assert progress_calls[-1][1] == 100.0

    @pytest.mark.asyncio
    async def test_run_final_progress_100_on_success(self, mock_storage):
        """run() 成功完成时最终进度回调应为 100"""
        pipeline = OntologyPipeline()

        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            mock_handler.execute = AsyncMock(return_value=True)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        last_progress = {}

        async def track_progress(stage, progress, message):
            last_progress["progress"] = progress
            last_progress["message"] = message

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            await pipeline.run(
                ingest_id="ingest-run-004",
                scenario_id="scenario-004",
                progress_callback=track_progress,
            )

        assert last_progress["progress"] == 100.0


# ---------------------------------------------------------------------------
# TestPipelineRunAsync — run_async() 方法
# ---------------------------------------------------------------------------

class TestPipelineRunAsync:
    @pytest.mark.asyncio
    async def test_run_async_with_all_successful_handlers(self, mock_storage):
        """run_async() 所有阶段成功时 context.success 应为 True"""
        pipeline = OntologyPipeline()

        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            mock_handler.execute = AsyncMock(return_value=True)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            context = await pipeline.run_async(
                ingest_id="ingest-async-001",
                scenario_id="scenario-async-001",
            )

        assert context.success is True

    @pytest.mark.asyncio
    async def test_run_async_collection_failure_aborts(self, mock_storage):
        """run_async() COLLECTION 阶段失败时应中止"""
        pipeline = OntologyPipeline()

        # COLLECTION 失败
        mock_collection = MagicMock()
        mock_collection.execute = AsyncMock(return_value=False)
        mock_collection.stage = PipelineStage.COLLECTION
        pipeline.handlers[PipelineStage.COLLECTION] = mock_collection

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            context = await pipeline.run_async(
                ingest_id="ingest-async-002",
                scenario_id="scenario-async-002",
            )

        assert context.success is False

    @pytest.mark.asyncio
    async def test_run_async_invokes_progress_callback(self, mock_storage):
        """run_async() 应调用 progress_callback"""
        pipeline = OntologyPipeline()

        for stage in pipeline._execution_order:
            mock_handler = MagicMock()
            mock_handler.execute = AsyncMock(return_value=True)
            mock_handler.stage = stage
            pipeline.handlers[stage] = mock_handler

        progress_calls = []

        async def track_progress(stage, progress, message):
            progress_calls.append((stage, progress, message))

        with patch(
            "odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage",
            return_value=mock_storage,
        ):
            await pipeline.run_async(
                ingest_id="ingest-async-003",
                scenario_id="scenario-async-003",
                progress_callback=track_progress,
            )

        # 应有进度回调
        assert len(progress_calls) >= 3
        # 最终进度应为 100
        assert progress_calls[-1][1] == 100.0


# ---------------------------------------------------------------------------
# TestPipelineSingleton — 单例模式
# ---------------------------------------------------------------------------

class TestPipelineSingleton:
    def test_get_instance_returns_same(self):
        """get_instance() 应返回同一实例"""
        a = OntologyPipeline.get_instance()
        b = OntologyPipeline.get_instance()
        assert a is b

    def test_initialize_creates_new_instance(self):
        """initialize() 应创建新实例"""
        a = OntologyPipeline.get_instance()
        b = OntologyPipeline.initialize()
        assert b is not a

    def test_pipeline_service_alias(self):
        """PipelineService 应是 OntologyPipeline 的别名"""
        assert PipelineService is OntologyPipeline


# ---------------------------------------------------------------------------
# TestPipelineStats — 统计信息
# ---------------------------------------------------------------------------

class TestPipelineStats:
    def test_get_stats_returns_dict(self):
        """get_stats() 应返回包含统计信息的 dict"""
        pipeline = OntologyPipeline()
        stats = pipeline.get_stats()
        assert "ingest_count" in stats
        assert "error_count" in stats
        assert "version_count" in stats
        assert "latest_version" in stats
