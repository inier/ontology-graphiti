"""Graphiti Core 事件集成

将 graphiti-core 的知识图谱操作事件接入结构化日志系统
支持实体创建、更新、删除，关系变化等事件追踪
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone

from .structured_logging import (
    LogLevel,
    LogSource,
    StructuredLogger,
    get_structured_logger,
)

logger = logging.getLogger("graphiti_events")


class GraphitiEventType(str):
    """Graphiti 事件类型"""
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    RELATION_CREATED = "relation_created"
    RELATION_UPDATED = "relation_updated"
    RELATION_DELETED = "relation_deleted"
    SNAPSHOT_CREATED = "snapshot_created"
    VERSION_CREATED = "version_created"
    TRIX_RECALLED = "trix_recalled"
    QUERY_EXECUTED = "query_executed"


class GraphitiEvent:
    """Graphiti 事件"""

    def __init__(
        self,
        event_type: str,
        workspace_id: str,
        entity_id: Optional[str] = None,
        relation_id: Optional[str] = None,
        version_id: Optional[str] = None,
        snapshot_time: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
    ):
        self.event_type = event_type
        self.workspace_id = workspace_id
        self.entity_id = entity_id
        self.relation_id = relation_id
        self.version_id = version_id
        self.snapshot_time = snapshot_time
        self.data = data or {}
        self.trace_id = trace_id
        self.span_id = span_id
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "workspace_id": self.workspace_id,
            "entity_id": self.entity_id,
            "relation_id": self.relation_id,
            "version_id": self.version_id,
            "snapshot_time": self.snapshot_time,
            "data": self.data,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "timestamp": self.timestamp.isoformat(),
        }


class GraphitiEventHandler:
    """Graphiti 事件处理器

    订阅 graphiti-core 的事件并转发到结构化日志系统
    """

    def __init__(self, structured_logger: Optional[StructuredLogger] = None):
        self.structured_logger = structured_logger or get_structured_logger()
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """注销事件处理器"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def emit(self, event: GraphitiEvent) -> None:
        """发射事件"""
        await self._event_queue.put(event)

    async def start(self) -> None:
        """启动事件处理器"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("GraphitiEventHandler started")

    async def stop(self) -> None:
        """停止事件处理器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("GraphitiEventHandler stopped")

    async def _process_events(self) -> None:
        """事件处理循环"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self._handle_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing graphiti event: {e}")

    async def _handle_event(self, event: GraphitiEvent) -> None:
        """处理单个事件"""
        await self.structured_logger.log(
            message=f"Graphiti event: {event.event_type}",
            level=LogLevel.INFO,
            source=LogSource.GRAPHTI_CORE,
            trace_id=event.trace_id,
            span_id=event.span_id,
            workspace_id=event.workspace_id,
            entity_id=event.entity_id,
            operation=event.event_type,
            metadata=event.data,
        )

        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")


class GraphitiEntityTracker:
    """Graphiti 实体追踪器

    追踪实体的生命周期事件并记录到时序数据库
    """

    def __init__(self, event_handler: Optional[GraphitiEventHandler] = None):
        self.event_handler = event_handler or GraphitiEventHandler()

    async def track_entity_created(
        self,
        workspace_id: str,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        properties: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> None:
        """追踪实体创建"""
        event = GraphitiEvent(
            event_type=GraphitiEventType.ENTITY_CREATED,
            workspace_id=workspace_id,
            entity_id=entity_id,
            data={
                "entity_type": entity_type,
                "entity_name": entity_name,
                "properties": properties,
                "property_count": len(properties),
            },
            trace_id=trace_id,
        )
        await self.event_handler.emit(event)

    async def track_entity_updated(
        self,
        workspace_id: str,
        entity_id: str,
        changes: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> None:
        """追踪实体更新"""
        event = GraphitiEvent(
            event_type=GraphitiEventType.ENTITY_UPDATED,
            workspace_id=workspace_id,
            entity_id=entity_id,
            data={
                "changes": changes,
                "changed_fields": list(changes.keys()),
            },
            trace_id=trace_id,
        )
        await self.event_handler.emit(event)

    async def track_relation_created(
        self,
        workspace_id: str,
        relation_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        properties: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> None:
        """追踪关系创建"""
        event = GraphitiEvent(
            event_type=GraphitiEventType.RELATION_CREATED,
            workspace_id=workspace_id,
            relation_id=relation_id,
            data={
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "relation_type": relation_type,
                "properties": properties,
            },
            trace_id=trace_id,
        )
        await self.event_handler.emit(event)

    async def track_version_created(
        self,
        workspace_id: str,
        version_id: str,
        version_number: int,
        snapshot_time: str,
        entity_count: int,
        relation_count: int,
        trace_id: Optional[str] = None,
    ) -> None:
        """追踪版本创建"""
        event = GraphitiEvent(
            event_type=GraphitiEventType.VERSION_CREATED,
            workspace_id=workspace_id,
            version_id=version_id,
            snapshot_time=snapshot_time,
            data={
                "version_number": version_number,
                "entity_count": entity_count,
                "relation_count": relation_count,
            },
            trace_id=trace_id,
        )
        await self.event_handler.emit(event)


_graphiti_event_handler: Optional[GraphitiEventHandler] = None


async def get_graphiti_event_handler() -> GraphitiEventHandler:
    """获取 Graphiti 事件处理器单例"""
    global _graphiti_event_handler
    if _graphiti_event_handler is None:
        _graphiti_event_handler = GraphitiEventHandler()
        await _graphiti_event_handler.start()
    return _graphiti_event_handler


async def shutdown_graphiti_event_handler() -> None:
    """关闭 Graphiti 事件处理器"""
    global _graphiti_event_handler
    if _graphiti_event_handler:
        await _graphiti_event_handler.stop()
        _graphiti_event_handler = None
