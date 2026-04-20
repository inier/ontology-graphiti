#!/usr/bin/env python3
"""
AuditLogger 审计日志器实现

符合设计文档 Phase 0 要求的 AuditLogger 实现，
支持多通道（SQLite + Graphiti）。
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from .audit_models import AuditEvent, AuditFilter, AuditSeverity, AuditEventType, ActorInfo, ResourceInfo, ActionResult
from .audit_sqlite_channel import AuditChannel, get_audit_channel
from .audit_graphiti_channel import GraphitiAuditChannel, get_graphiti_audit_channel
from .audit_span import AuditSpan


class AuditSampler:
    """审计日志采样器"""

    def should_sample(self, event: AuditEvent) -> bool:
        """判断是否应该采样"""
        return event.severity != AuditSeverity.DEBUG


class AuditEnricher:
    """审计日志丰富器"""

    async def enrich(self, event: AuditEvent) -> AuditEvent:
        """丰富审计事件"""
        return event


class WorkspaceEnricher(AuditEnricher):
    """工作空间信息丰富器"""

    async def enrich(self, event: AuditEvent) -> AuditEvent:
        """丰富工作空间信息"""
        if not event.workspace_id or event.workspace_id == "default":
            event.workspace_id = "default"
        return event


class TraceEnricher(AuditEnricher):
    """分布式追踪信息丰富器"""

    async def enrich(self, event: AuditEvent) -> AuditEvent:
        """丰富分布式追踪信息"""
        if not event.trace_id:
            event.trace_id = str(uuid.uuid4())
        return event


class AuditLogger:
    """
    审计日志器 - 统一入口

    特性：
    - 异步写入，不阻塞业务线程
    - 支持多通道（SQLite 主存储 + Graphiti 补充存储）
    - 支持批量聚合（减少 I/O）
    - 内置采样（DEBUG 级别可采样）
    - 与 WorkspaceContext 自动绑定
    """

    def __init__(
        self,
        channel: Optional[AuditChannel] = None,
        graphiti_channel: Optional[GraphitiAuditChannel] = None,
        sampler: Optional[AuditSampler] = None,
        enrichers: Optional[List[AuditEnricher]] = None,
        enable_graphiti: bool = True,
    ):
        """
        初始化审计日志器

        Args:
            channel: SQLite 审计通道（主存储）
            graphiti_channel: Graphiti 审计通道（补充存储）
            sampler: 采样器
            enrichers: 丰富器列表
            enable_graphiti: 是否启用 Graphiti
        """
        self._channel = channel or get_audit_channel()
        self._graphiti_channel = graphiti_channel if graphiti_channel else (get_graphiti_audit_channel() if enable_graphiti else None)
        self._sampler = sampler or AuditSampler()
        self._enrichers = enrichers or [WorkspaceEnricher(), TraceEnricher()]
        self._trace_id: str = str(uuid.uuid4())
        self._spans: Dict[str, AuditSpan] = {}

    async def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource: ResourceInfo,
        result: ActionResult,
        *,
        severity: AuditSeverity = AuditSeverity.INFO,
        source: str = "system",
        actor: Optional[ActorInfo] = None,
        context: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> AuditEvent:
        """记录审计事件"""
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            actor=actor or ActorInfo(
                actor_type="system",
                actor_id="system",
                actor_name="System",
                roles=[]
            ),
            action=action,
            resource=resource,
            result=result,
            context=context or {},
            workspace_id=workspace_id or "default",
            trace_id=trace_id or self._trace_id,
            parent_event_id=parent_event_id,
            duration_ms=duration_ms
        )

        for enricher in self._enrichers:
            event = await enricher.enrich(event)

        if not self._sampler.should_sample(event):
            return event

        await self._channel.write(event)

        if self._graphiti_channel:
            await self._graphiti_channel.write(event)

        return event

    async def log_event(self, event: AuditEvent) -> AuditEvent:
        """记录完整的审计事件对象"""
        for enricher in self._enrichers:
            event = await enricher.enrich(event)

        if not self._sampler.should_sample(event):
            return event

        await self._channel.write(event)

        if self._graphiti_channel:
            await self._graphiti_channel.write(event)

        return event

    async def log_batch(self, events: List[AuditEvent]) -> None:
        """批量记录审计事件"""
        enriched_events = []
        for event in events:
            for enricher in self._enrichers:
                event = await enricher.enrich(event)
            if self._sampler.should_sample(event):
                enriched_events.append(event)

        if enriched_events:
            await self._channel.write_batch(enriched_events)
            if self._graphiti_channel:
                await self._graphiti_channel.write_batch(enriched_events)

    def start_span(self, event_type: AuditEventType, action: str, **kwargs) -> AuditSpan:
        """创建审计跨度"""
        span = AuditSpan(self, event_type, action, **kwargs)
        self._spans[span.span_id] = span
        return span

    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件（从 SQLite 主存储）"""
        return await self._channel.query(filter)

    async def query_graphiti(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件（从 Graphiti）"""
        if self._graphiti_channel:
            return await self._graphiti_channel.query(filter)
        return []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {}
        if hasattr(self._channel, 'get_stats'):
            stats = self._channel.get_stats()
        if self._graphiti_channel and hasattr(self._graphiti_channel, 'get_stats'):
            graphiti_stats = self._graphiti_channel.get_stats()
            stats["graphiti"] = graphiti_stats
        return stats

    def close(self) -> None:
        """关闭审计日志器"""
        if hasattr(self._channel, 'close_sync'):
            self._channel.close_sync()
        elif hasattr(self._channel, 'close'):
            self._channel.close()

    async def log_success(
        self,
        event_type: AuditEventType,
        action: str,
        resource: ResourceInfo,
        message: str = "",
        **kwargs
    ) -> AuditEvent:
        """记录成功事件"""
        result = ActionResult(status="success", message=message)
        return await self.log(event_type, action, resource, result, **kwargs)

    async def log_failure(
        self,
        event_type: AuditEventType,
        action: str,
        resource: ResourceInfo,
        message: str,
        error_code: Optional[str] = None,
        **kwargs
    ) -> AuditEvent:
        """记录失败事件"""
        result = ActionResult(status="failure", message=message, error_code=error_code)
        return await self.log(event_type, action, resource, result, severity=AuditSeverity.ERROR, **kwargs)

    async def log_denied(
        self,
        event_type: AuditEventType,
        action: str,
        resource: ResourceInfo,
        message: str = "Access denied",
        **kwargs
    ) -> AuditEvent:
        """记录被拒绝的事件"""
        result = ActionResult(status="denied", message=message)
        return await self.log(event_type, action, resource, result, severity=AuditSeverity.WARN, **kwargs)


_audit_logger_instance = None


def get_audit_logger(**kwargs) -> AuditLogger:
    """获取审计日志器实例"""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger(**kwargs)
    return _audit_logger_instance


def reset_audit_logger():
    """重置全局审计日志器实例"""
    global _audit_logger_instance
    if _audit_logger_instance:
        _audit_logger_instance.close()
    _audit_logger_instance = None


def run_sync(coro, *args, **kwargs):
    """同步运行协程"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.run_until_complete(coro(*args, **kwargs))
        else:
            return loop.run_until_complete(coro(*args, **kwargs))
    except RuntimeError:
        return asyncio.run(coro(*args, **kwargs))


__all__ = [
    'AuditLogger',
    'AuditSampler',
    'AuditEnricher',
    'WorkspaceEnricher',
    'TraceEnricher',
    'get_audit_logger',
    'reset_audit_logger',
    'run_sync'
]
