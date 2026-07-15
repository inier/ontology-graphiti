"""infra/logging 模块单元测试

覆盖：
- odap/infra/logging/structured_logging.py — 结构化日志记录器
- odap/infra/logging/graphiti_events.py — Graphiti 事件集成

验证点：
- StructuredLogRecord 序列化（to_dict / to_json）
- LogLevel / LogSource 枚举为 (str, Enum) 双继承
- TimeSeriesLogHandler 缓冲与刷新（memory 后端）
- StructuredLogger 单例 + 上下文 + 各级别日志
- GraphitiEvent 序列化
- GraphitiEventType 事件类型常量
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. 枚举验证
# ============================================================


class TestLogEnums:
    """日志枚举类型验证。"""

    def test_log_level_is_str_enum(self):
        """LogLevel 必须为 (str, Enum) 双继承（AGENTS.md 规则 4）。"""
        from odap.infra.logging.structured_logging import LogLevel

        assert issubclass(LogLevel, str)
        assert LogLevel.INFO == "info"
        assert LogLevel.ERROR.value == "error"

    def test_log_source_is_str_enum(self):
        """LogSource 必须为 (str, Enum) 双继承。"""
        from odap.infra.logging.structured_logging import LogSource

        assert issubclass(LogSource, str)
        assert LogSource.AGENT == "agent"
        assert LogSource.ONTOLOGY.value == "ontology"

    def test_log_level_values_complete(self):
        """日志级别值完整。"""
        from odap.infra.logging.structured_logging import LogLevel

        levels = {lv.value for lv in LogLevel}
        assert {"trace", "debug", "info", "warning", "error", "critical"} <= levels


# ============================================================
# 2. StructuredLogRecord
# ============================================================


class TestStructuredLogRecord:
    """结构化日志记录。"""

    def test_record_generates_id_and_timestamp(self):
        """记录自动生成 id 与 timestamp。"""
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        rec = StructuredLogRecord(
            message="test", level=LogLevel.INFO, source=LogSource.SYSTEM
        )
        assert rec.id  # uuid 自动生成
        assert rec.timestamp is not None
        assert rec.trace_id  # 自动生成
        assert rec.span_id  # 自动生成

    def test_record_to_dict_contains_all_fields(self):
        """to_dict 包含所有字段。"""
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        rec = StructuredLogRecord(
            message="hello",
            level=LogLevel.WARNING,
            source=LogSource.AGENT,
            workspace_id="ws-1",
            user_id="u1",
            operation="query",
            duration_ms=12.5,
            metadata={"key": "val"},
        )
        d = rec.to_dict()
        assert d["message"] == "hello"
        assert d["level"] == "warning"
        assert d["source"] == "agent"
        assert d["workspace_id"] == "ws-1"
        assert d["duration_ms"] == 12.5
        assert d["metadata"] == {"key": "val"}
        assert "id" in d
        assert "timestamp" in d
        assert "trace_id" in d

    def test_record_to_json_is_valid_json(self):
        """to_json 返回合法 JSON。"""
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        rec = StructuredLogRecord(
            message="中文测试",
            level=LogLevel.INFO,
            source=LogSource.SYSTEM,
        )
        s = rec.to_json()
        parsed = json.loads(s)
        assert parsed["message"] == "中文测试"

    def test_record_metadata_defaults_to_empty_dict(self):
        """metadata 默认为空 dict（非 None）。"""
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        rec = StructuredLogRecord(
            message="x", level=LogLevel.INFO, source=LogSource.SYSTEM
        )
        assert rec.metadata == {}

    def test_record_with_error_dict(self):
        """error 字段可携带错误信息。"""
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        rec = StructuredLogRecord(
            message="fail",
            level=LogLevel.ERROR,
            source=LogSource.SYSTEM,
            error={"type": "ValueError", "message": "bad input"},
        )
        assert rec.error["type"] == "ValueError"


# ============================================================
# 3. TimeSeriesLogHandler（memory 后端）
# ============================================================


class TestTimeSeriesLogHandler:
    """时序日志处理器（使用 memory 后端，无外部依赖）。"""

    @pytest.fixture
    def handler(self):
        from odap.infra.logging.structured_logging import TimeSeriesLogHandler

        return TimeSeriesLogHandler(backend="memory")

    @pytest.fixture
    def make_record(self):
        from odap.infra.logging.structured_logging import (
            LogLevel,
            LogSource,
            StructuredLogRecord,
        )

        def _factory(message="test", level=LogLevel.INFO):
            return StructuredLogRecord(
                message=message, level=level, source=LogSource.SYSTEM
            )

        return _factory

    async def test_write_buffers_records(self, handler, make_record):
        """write 将记录加入缓冲区。"""
        rec = make_record()
        await handler.write(rec)
        assert len(handler._buffer) == 1

    async def test_write_batch_extends_buffer(self, handler, make_record):
        """write_batch 批量加入缓冲区。"""
        records = [make_record(f"msg-{i}") for i in range(5)]
        await handler.write_batch(records)
        assert len(handler._buffer) == 5

    async def test_flush_clears_buffer(self, handler, make_record):
        """flush 清空缓冲区。"""
        for i in range(3):
            await handler.write(make_record(f"msg-{i}"))
        assert len(handler._buffer) == 3
        await handler.flush()
        assert len(handler._buffer) == 0

    async def test_flush_empty_buffer_noop(self, handler):
        """flush 空缓冲区为 no-op。"""
        await handler.flush()  # 不应抛异常
        assert len(handler._buffer) == 0

    async def test_unsupported_backend_raises_on_init(self):
        """不支持的 backend 在 initialize 时抛 ValueError。"""
        from odap.infra.logging.structured_logging import TimeSeriesLogHandler

        h = TimeSeriesLogHandler(backend="unknown")
        with pytest.raises(ValueError, match="Unsupported backend"):
            await h.initialize()


# ============================================================
# 4. StructuredLogger
# ============================================================


class TestStructuredLogger:
    """结构化日志记录器。"""

    @pytest.fixture
    def logger(self):
        from odap.infra.logging.structured_logging import StructuredLogger

        return StructuredLogger()

    def test_get_instance_singleton(self):
        """get_instance 返回单例。"""
        from odap.infra.logging.structured_logging import StructuredLogger

        a = StructuredLogger.get_instance()
        b = StructuredLogger.get_instance()
        assert a is b

    def test_set_and_clear_context(self, logger):
        """上下文设置与清除。"""
        logger.set_context(workspace_id="ws-1", user_id="u1")
        assert logger._context["workspace_id"] == "ws-1"
        logger.clear_context()
        assert logger._context == {}

    async def test_log_writes_to_handler(self, logger):
        """log 方法将记录写入 handler。"""
        logger.handler = MagicMock()
        logger.handler.write = AsyncMock()
        await logger.info("hello", workspace_id="ws-1")
        logger.handler.write.assert_awaited_once()
        rec = logger.handler.write.call_args[0][0]
        assert rec.message == "hello"

    async def test_error_level_records_error_dict(self, logger):
        """error 级别日志携带 error dict。"""
        logger.handler = MagicMock()
        logger.handler.write = AsyncMock()
        err = ValueError("bad input")
        await logger.error("fail", error=err)
        rec = logger.handler.write.call_args[0][0]
        assert rec.error is not None
        assert rec.error["type"] == "ValueError"
        assert rec.error["message"] == "bad input"

    async def test_all_log_levels(self, logger):
        """所有日志级别均可调用。"""
        logger.handler = MagicMock()
        logger.handler.write = AsyncMock()
        await logger.trace("t")
        await logger.debug("d")
        await logger.info("i")
        await logger.warning("w")
        await logger.error("e")
        await logger.critical("c")
        assert logger.handler.write.await_count == 6


# ============================================================
# 5. Graphiti 事件
# ============================================================


class TestGraphitiEvents:
    """Graphiti 事件集成。"""

    def test_event_type_constants(self):
        """事件类型常量完整。"""
        from odap.infra.logging.graphiti_events import GraphitiEventType

        assert GraphitiEventType.ENTITY_CREATED == "entity_created"
        assert GraphitiEventType.RELATION_DELETED == "relation_deleted"
        assert GraphitiEventType.QUERY_EXECUTED == "query_executed"

    def test_event_to_dict_contains_all_fields(self):
        """GraphitiEvent.to_dict 包含所有字段。"""
        from odap.infra.logging.graphiti_events import GraphitiEvent

        ev = GraphitiEvent(
            event_type="entity_created",
            workspace_id="ws-1",
            entity_id="e-1",
            data={"name": "Customer"},
            trace_id="t-1",
            span_id="s-1",
        )
        d = ev.to_dict()
        assert d["event_type"] == "entity_created"
        assert d["workspace_id"] == "ws-1"
        assert d["entity_id"] == "e-1"
        assert d["data"] == {"name": "Customer"}
        assert d["trace_id"] == "t-1"
        assert "timestamp" in d

    def test_event_data_defaults_to_empty_dict(self):
        """data 默认为空 dict。"""
        from odap.infra.logging.graphiti_events import GraphitiEvent

        ev = GraphitiEvent(event_type="x", workspace_id="ws-1")
        assert ev.data == {}

    def test_event_timestamp_is_utc(self):
        """timestamp 为 UTC 时间。"""
        from odap.infra.logging.graphiti_events import GraphitiEvent

        ev = GraphitiEvent(event_type="x", workspace_id="ws-1")
        assert ev.timestamp.tzinfo is not None
