#!/usr/bin/env python3
"""
统一审计日志系统

符合设计文档 Phase 0 要求的统一审计系统
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from .audit_mongodb_channel import get_audit_channel, AuditChannel
from .audit_models import AuditEvent, AuditFilter, AuditSeverity, AuditEventType

_audit_logger_instance = None


class AuditLogger:
    """
    审计日志记录器

    符合设计文档 Phase 0 要求：
    - 支持同步和异步接口
    - 支持结构化字段
    - 支持批量操作
    - 支持防篡改校验
    - 支持多通道输出
    """

    def __init__(self, channel: Optional[AuditChannel] = None):
        """
        初始化审计日志记录器

        Args:
            channel: 审计通道实例
        """
        self.channel = channel or get_audit_channel()

    async def log(self,
                 event_type: AuditEventType,
                 severity: AuditSeverity,
                 actor: Dict[str, Any],
                 action: str,
                 resource: Dict[str, Any],
                 result: Dict[str, Any],
                 workspace_id: str,
                 trace_id: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None,
                 parent_event_id: Optional[str] = None,
                 duration_ms: Optional[int] = None,
                 source: str = "system") -> str:
        """
        异步记录审计事件

        Args:
            event_type: 事件类型
            severity: 严重程度
            actor: 执行主体
            action: 操作
            resource: 资源
            result: 结果
            workspace_id: 工作空间 ID
            trace_id: 追踪 ID
            context: 上下文
            parent_event_id: 父事件 ID
            duration_ms: 持续时间
            source: 来源

        Returns:
            str: 事件 ID
        """
        event = AuditEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            source=source,
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            context=context or {},
            workspace_id=workspace_id,
            trace_id=trace_id or str(uuid.uuid4()),
            parent_event_id=parent_event_id,
            duration_ms=duration_ms
        )

        await self.channel.write(event)
        return event.id

    def log_sync(self,
                event_type: AuditEventType,
                severity: AuditSeverity,
                actor: Dict[str, Any],
                action: str,
                resource: Dict[str, Any],
                result: Dict[str, Any],
                workspace_id: str,
                trace_id: Optional[str] = None,
                context: Optional[Dict[str, Any]] = None,
                parent_event_id: Optional[str] = None,
                duration_ms: Optional[int] = None,
                source: str = "system") -> str:
        """
        同步记录审计事件

        Args:
            event_type: 事件类型
            severity: 严重程度
            actor: 执行主体
            action: 操作
            resource: 资源
            result: 结果
            workspace_id: 工作空间 ID
            trace_id: 追踪 ID
            context: 上下文
            parent_event_id: 父事件 ID
            duration_ms: 持续时间
            source: 来源

        Returns:
            str: 事件 ID
        """
        event = AuditEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            source=source,
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            context=context or {},
            workspace_id=workspace_id,
            trace_id=trace_id or str(uuid.uuid4()),
            parent_event_id=parent_event_id,
            duration_ms=duration_ms
        )

        try:
            asyncio.run(self.channel.write(event))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.channel.write(event))

        return event.id

    async def log_batch(self, events: List[AuditEvent]) -> List[str]:
        """
        批量记录审计事件

        Args:
            events: 审计事件列表

        Returns:
            List[str]: 事件 ID 列表
        """
        await self.channel.write_batch(events)
        return [event.id for event in events]

    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """
        查询审计事件

        Args:
            filter: 查询过滤器

        Returns:
            List[AuditEvent]: 审计事件列表
        """
        return await self.channel.query(filter)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取审计统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return self.channel.get_stats()

    async def close(self):
        """
        关闭审计通道
        """
        await self.channel.close()

    def close_sync(self):
        """
        同步关闭审计通道
        """
        self.channel.close_sync()


def get_audit_logger(channel: Optional[AuditChannel] = None) -> AuditLogger:
    """
    获取审计日志记录器实例

    Args:
        channel: 审计通道实例

    Returns:
        AuditLogger: 审计日志记录器实例
    """
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger(channel)
    return _audit_logger_instance


def audit_info(event_type: AuditEventType, actor: Dict[str, Any], action: str,
              resource: Dict[str, Any], result: Dict[str, Any], workspace_id: str,
              **kwargs) -> str:
    """
    记录信息级别审计事件

    Args:
        event_type: 事件类型
        actor: 执行主体
        action: 操作
        resource: 资源
        result: 结果
        workspace_id: 工作空间 ID
        **kwargs: 其他参数

    Returns:
        str: 事件 ID
    """
    logger = get_audit_logger()
    return logger.log_sync(event_type, AuditSeverity.INFO, actor, action,
                         resource, result, workspace_id, **kwargs)


def audit_warning(event_type: AuditEventType, actor: Dict[str, Any], action: str,
                 resource: Dict[str, Any], result: Dict[str, Any], workspace_id: str,
                 **kwargs) -> str:
    """
    记录警告级别审计事件

    Args:
        event_type: 事件类型
        actor: 执行主体
        action: 操作
        resource: 资源
        result: 结果
        workspace_id: 工作空间 ID
        **kwargs: 其他参数

    Returns:
        str: 事件 ID
    """
    logger = get_audit_logger()
    return logger.log_sync(event_type, AuditSeverity.WARNING, actor, action,
                         resource, result, workspace_id, **kwargs)


def audit_error(event_type: AuditEventType, actor: Dict[str, Any], action: str,
               resource: Dict[str, Any], result: Dict[str, Any], workspace_id: str,
               **kwargs) -> str:
    """
    记录错误级别审计事件

    Args:
        event_type: 事件类型
        actor: 执行主体
        action: 操作
        resource: 资源
        result: 结果
        workspace_id: 工作空间 ID
        **kwargs: 其他参数

    Returns:
        str: 事件 ID
    """
    logger = get_audit_logger()
    return logger.log_sync(event_type, AuditSeverity.ERROR, actor, action,
                         resource, result, workspace_id, **kwargs)


def audit_critical(event_type: AuditEventType, actor: Dict[str, Any], action: str,
                  resource: Dict[str, Any], result: Dict[str, Any], workspace_id: str,
                  **kwargs) -> str:
    """
    记录严重级别审计事件

    Args:
        event_type: 事件类型
        actor: 执行主体
        action: 操作
        resource: 资源
        result: 结果
        workspace_id: 工作空间 ID
        **kwargs: 其他参数

    Returns:
        str: 事件 ID
    """
    logger = get_audit_logger()
    return logger.log_sync(event_type, AuditSeverity.CRITICAL, actor, action,
                         resource, result, workspace_id, **kwargs)


__all__ = [
    'AuditLogger',
    'get_audit_logger',
    'audit_info',
    'audit_warning',
    'audit_error',
    'audit_critical'
]