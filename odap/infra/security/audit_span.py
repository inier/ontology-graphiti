#!/usr/bin/env python3
"""
AuditSpan 耗时追踪实现

符合设计文档 Phase 0 要求的 AuditSpan 实现
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from .audit_models import AuditEvent, AuditSeverity, AuditEventType

if TYPE_CHECKING:
    from .audit_logger_v2 import AuditLoggerV2 as AuditLogger


class AuditSpan:
    """
    审计跨度 - 追踪耗时操作
    
    符合设计文档 Phase 0 要求：
    - 自动记录开始/结束时间
    - 计算耗时
    - 支持嵌套（形成因果链）
    """
    
    def __init__(self, logger: 'AuditLogger', event_type: AuditEventType, action: str, **kwargs):
        """
        初始化审计跨度
        
        Args:
            logger: 审计日志器实例
            event_type: 事件类型
            action: 操作动作
            **kwargs: 额外参数
        """
        self._logger = logger
        self._event_type = event_type
        self._action = action
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._duration_ms: Optional[int] = None
        self._result: Optional[Dict[str, Any]] = None
        self._parent: Optional[AuditSpan] = None
        self._children: List[AuditSpan] = []
        self._span_id: str = kwargs.get('span_id', f"span_{id(self)}")
        self._trace_id: str = kwargs.get('trace_id')
        self._parent_event_id: str = kwargs.get('parent_event_id')
        self._workspace_id: str = kwargs.get('workspace_id', 'default')
        self._actor_id: str = kwargs.get('actor_id', 'system')
        self._actor_name: str = kwargs.get('actor_name', 'System')
        self._resource_type: str = kwargs.get('resource_type', 'span')
        self._resource_id: str = kwargs.get('resource_id', self._span_id)
        self._resource_name: str = kwargs.get('resource_name', 'AuditSpan')
        self._context: Dict[str, Any] = kwargs.get('context', {})
    
    @property
    def span_id(self) -> str:
        """获取跨度ID"""
        return self._span_id
    
    @property
    def trace_id(self) -> Optional[str]:
        """获取追踪ID"""
        return self._trace_id or (self._parent.trace_id if self._parent else None)
    
    @property
    def parent_event_id(self) -> Optional[str]:
        """获取父事件ID"""
        return self._parent_event_id or (self._parent.span_id if self._parent else None)
    
    @property
    def duration_ms(self) -> Optional[int]:
        """获取耗时（毫秒）"""
        return self._duration_ms
    
    def child_span(self, event_type: AuditEventType, action: str, **kwargs) -> 'AuditSpan':
        """创建子跨度
        
        Args:
            event_type: 事件类型
            action: 操作动作
            **kwargs: 额外参数
            
        Returns:
            AuditSpan: 子跨度实例
        """
        child = AuditSpan(
            logger=self._logger,
            event_type=event_type,
            action=action,
            trace_id=self.trace_id,
            parent_event_id=self._span_id,
            workspace_id=self._workspace_id,
            actor_id=self._actor_id,
            actor_name=self._actor_name,
            **kwargs
        )
        child._parent = self
        self._children.append(child)
        return child
    
    def set_result(self, status: str = 'success', message: str = '', **kwargs):
        """设置操作结果
        
        Args:
            status: 状态（success/failure/denied）
            message: 结果描述
            **kwargs: 额外结果信息
        """
        self._result = {
            'status': status,
            'message': message,
            **kwargs
        }
    
    def set_context(self, **context):
        """设置上下文信息
        
        Args:
            **context: 上下文信息
        """
        self._context.update(context)
    
    async def __aenter__(self) -> 'AuditSpan':
        """进入上下文管理器"""
        self._start_time = datetime.now()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器"""
        self._end_time = datetime.now()
        
        # 计算耗时
        if self._start_time:
            duration = (self._end_time - self._start_time).total_seconds() * 1000
            self._duration_ms = int(duration)
        
        # 处理异常
        if exc_type:
            if not self._result:
                self._result = {
                    'status': 'failure',
                    'message': str(exc_val),
                    'error_code': exc_type.__name__
                }
        
        # 确保结果存在
        if not self._result:
            self._result = {
                'status': 'success',
                'message': ''
            }
        
        # 记录审计事件
        await self._log_event()
    
    async def _log_event(self):
        """记录审计事件"""
        # 构建审计事件
        from .audit_models import ActorInfo, ResourceInfo, ActionResult
        
        event = AuditEvent(
            event_type=self._event_type,
            severity=AuditSeverity.INFO,
            source="audit_span",
            actor=ActorInfo(
                actor_type="system",
                actor_id=self._actor_id,
                actor_name=self._actor_name,
                roles=[]
            ),
            action=self._action,
            resource=ResourceInfo(
                resource_type=self._resource_type,
                resource_id=self._resource_id,
                resource_name=self._resource_name,
                attributes={}
            ),
            result=ActionResult(
                status=self._result['status'],
                message=self._result['message'],
                error_code=self._result.get('error_code'),
                changes=self._result.get('changes')
            ),
            context={
                'span_id': self._span_id,
                'trace_id': self.trace_id,
                'parent_event_id': self.parent_event_id,
                'child_count': len(self._children),
                **self._context
            },
            workspace_id=self._workspace_id,
            trace_id=self.trace_id or self._logger._trace_id,
            parent_event_id=self.parent_event_id,
            duration_ms=self._duration_ms
        )
        
        # 记录事件
        await self._logger.log_event(event)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"AuditSpan({self._event_type}, {self._action}, {self._duration_ms}ms)"
    
    def __repr__(self) -> str:
        """官方表示"""
        return f"AuditSpan(event_type='{self._event_type}', action='{self._action}', span_id='{self._span_id}')"


__all__ = [
    'AuditSpan'
]
