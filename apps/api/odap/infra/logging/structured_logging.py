"""结构化日志系统

整合 graphiti-core 知识图谱事件与时序数据库存储
支持 OpenTelemetry 标准追踪上下文
"""

import json
import logging
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from enum import Enum

logger = logging.getLogger("structured_logging")


class LogLevel(str, Enum):
    """日志级别"""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogSource(str, Enum):
    """日志来源"""
    GRAPHTI_CORE = "graphiti_core"
    ONTOLOGY = "ontology"
    WORKSPACE = "workspace"
    AGENT = "agent"
    DECISION = "decision"
    AUDIT = "audit"
    SYSTEM = "system"


class StructuredLogRecord:
    """结构化日志记录"""

    def __init__(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc)
        self.message = message
        self.level = level
        self.source = source
        self.trace_id = trace_id or self._generate_trace_id()
        self.span_id = span_id or self._generate_span_id()
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.entity_id = entity_id
        self.operation = operation
        self.duration_ms = duration_ms
        self.metadata = metadata or {}
        self.error = error

    @staticmethod
    def _generate_trace_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _generate_span_id() -> str:
        return uuid.uuid4().hex[:8]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "level": self.level.value,
            "source": self.source.value,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "entity_id": self.entity_id,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class TimeSeriesLogHandler:
    """时序数据库日志处理器

    支持 InfluxDB 和 TimescaleDB (PostgreSQL) 两种后端
    """

    def __init__(
        self,
        backend: str = "influxdb",
        connection_url: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.backend = backend
        self.connection_url = connection_url
        self.org = org
        self.bucket = bucket
        self.token = token
        self._client = None
        self._buffer: List[StructuredLogRecord] = []
        self._buffer_size = 100
        self._flush_interval = 5.0
        self._last_flush = datetime.now(timezone.utc)

    async def initialize(self) -> None:
        """初始化连接"""
        if self.backend == "influxdb":
            await self._init_influxdb()
        elif self.backend == "timescale":
            await self._init_timescale()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    async def _init_influxdb(self) -> None:
        """初始化 InfluxDB 连接"""
        try:
            from influxdb_client import InfluxDBClient

            self._client = InfluxDBClient(
                url=self.connection_url or "http://localhost:8086",
                org=self.org or "odap",
                bucket=self.bucket or "logs",
                token=self.token or "token",
            )
            logger.info("InfluxDB log handler initialized")
        except ImportError:
            logger.warning("influxdb-client not installed, using fallback handler")
            self.backend = "memory"

    async def _init_timescale(self) -> None:
        """初始化 TimescaleDB 连接"""
        try:
            import asyncpg

            self._client = await asyncpg.connect(self.connection_url or "postgresql://localhost:5432/odap")
            logger.info("TimescaleDB log handler initialized")
        except ImportError:
            logger.warning("asyncpg not installed, using fallback handler")
            self.backend = "memory"

    async def write(self, record: StructuredLogRecord) -> None:
        """写入单条日志"""
        self._buffer.append(record)

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

        elapsed = (datetime.now(timezone.utc) - self._last_flush).total_seconds()
        if elapsed >= self._flush_interval:
            await self.flush()

    async def write_batch(self, records: List[StructuredLogRecord]) -> None:
        """批量写入日志"""
        self._buffer.extend(records)

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """刷新缓冲区到存储"""
        if not self._buffer:
            return

        records_to_write = self._buffer[:]
        self._buffer.clear()
        self._last_flush = datetime.now(timezone.utc)

        if self.backend == "influxdb":
            await self._flush_influxdb(records_to_write)
        elif self.backend == "timescale":
            await self._flush_timescale(records_to_write)
        else:
            self._flush_memory(records_to_write)

    async def _flush_influxdb(self, records: List[StructuredLogRecord]) -> None:
        """刷新到 InfluxDB"""
        try:
            from influxdb_client import Point
            from influxdb_client.client.write_api import WriteApiSyn

            write_api = self._client.write_api()
            points = []

            for record in records:
                point = Point("structured_logs") \
                    .tag("source", record.source.value) \
                    .tag("level", record.level.value) \
                    .tag("workspace_id", record.workspace_id or "none") \
                    .field("message", record.message) \
                    .field("trace_id", record.trace_id) \
                    .field("span_id", record.span_id) \
                    .field("user_id", record.user_id or "") \
                    .field("entity_id", record.entity_id or "") \
                    .field("operation", record.operation or "") \
                    .field("duration_ms", record.duration_ms or 0.0) \
                    .field("metadata", json.dumps(record.metadata)) \
                    .field("error", json.dumps(record.error) if record.error else "")

                if record.error:
                    point = point.tag("has_error", "true")

                points.append(point)

            write_api.write(bucket=self.bucket, org=self.org, record=points)
            logger.debug(f"Flushed {len(points)} logs to InfluxDB")

        except Exception as e:
            logger.error(f"Failed to flush to InfluxDB: {e}")
            self._buffer.extend(records)

    async def _flush_timescale(self, records: List[StructuredLogRecord]) -> None:
        """刷新到 TimescaleDB"""
        try:
            values = []
            for record in records:
                values.append((
                    record.timestamp,
                    record.id,
                    record.level.value,
                    record.source.value,
                    record.trace_id,
                    record.span_id,
                    record.workspace_id,
                    record.user_id,
                    record.entity_id,
                    record.operation,
                    record.duration_ms,
                    json.dumps(record.metadata),
                    json.dumps(record.error) if record.error else None,
                    record.message,
                ))

            await self._client.executemany("""
                INSERT INTO structured_logs (
                    timestamp, id, level, source, trace_id, span_id,
                    workspace_id, user_id, entity_id, operation,
                    duration_ms, metadata, error, message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """, values)

            logger.debug(f"Flushed {len(values)} logs to TimescaleDB")

        except Exception as e:
            logger.error(f"Failed to flush to TimescaleDB: {e}")
            self._buffer.extend(records)

    def _flush_memory(self, records: List[StructuredLogRecord]) -> None:
        """内存回退（仅用于开发/调试）"""
        for record in records:
            log_line = f"[{record.timestamp.isoformat()}] {record.level.value.upper()} [{record.source.value}] {record.message}"
            if record.error:
                log_line += f" | error: {json.dumps(record.error)}"
            logger.info(log_line)

    async def close(self) -> None:
        """关闭连接"""
        await self.flush()
        if self._client:
            if self.backend == "influxdb":
                self._client.close()
            elif self.backend == "timescale":
                await self._client.close()


class StructuredLogger:
    """结构化日志记录器"""

    _instance: Optional["StructuredLogger"] = None

    def __init__(self, handler: Optional[TimeSeriesLogHandler] = None):
        self.handler = handler or TimeSeriesLogHandler(backend="memory")
        self._context: Dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> "StructuredLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def initialize(
        cls,
        backend: str = "influxdb",
        **kwargs
    ) -> "StructuredLogger":
        instance = cls.get_instance()
        instance.handler = TimeSeriesLogHandler(
            backend=backend,
            **kwargs
        )
        await instance.handler.initialize()
        return instance

    def set_context(self, **kwargs) -> None:
        """设置日志上下文"""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """清除日志上下文"""
        self._context.clear()

    def _build_record(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[Exception] = None,
        **metadata
    ) -> StructuredLogRecord:
        context = {**self._context, **metadata}

        error_dict = None
        if error:
            error_dict = {
                "type": type(error).__name__,
                "message": str(error),
            }

        return StructuredLogRecord(
            message=message,
            level=level,
            source=source,
            trace_id=trace_id,
            span_id=span_id,
            workspace_id=workspace_id,
            user_id=user_id,
            entity_id=entity_id,
            operation=operation,
            duration_ms=duration_ms,
            metadata=context,
            error=error_dict,
        )

    async def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.SYSTEM,
        **kwargs
    ) -> None:
        record = self._build_record(message, level, source, **kwargs)
        await self.handler.write(record)

    async def trace(self, message: str, **kwargs) -> None:
        await self.log(message, LogLevel.TRACE, **kwargs)

    async def debug(self, message: str, **kwargs) -> None:
        await self.log(message, LogLevel.DEBUG, **kwargs)

    async def info(self, message: str, **kwargs) -> None:
        await self.log(message, LogLevel.INFO, **kwargs)

    async def warning(self, message: str, **kwargs) -> None:
        await self.log(message, LogLevel.WARNING, **kwargs)

    async def error(self, message: str, error: Optional[Exception] = None, **kwargs) -> None:
        await self.log(message, LogLevel.ERROR, error=error, **kwargs)

    async def critical(self, message: str, error: Optional[Exception] = None, **kwargs) -> None:
        await self.log(message, LogLevel.CRITICAL, error=error, **kwargs)


async def get_structured_logger() -> StructuredLogger:
    """获取结构化日志记录器实例"""
    return StructuredLogger.get_instance()


async def initialize_structured_logging(
    backend: str = "influxdb",
    **kwargs
) -> StructuredLogger:
    """初始化结构化日志系统"""
    return await StructuredLogger.initialize(backend=backend, **kwargs)
