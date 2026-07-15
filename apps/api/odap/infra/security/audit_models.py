#!/usr/bin/env python3
"""
审计日志核心模型

基于设计文档实现的完整审计事件模型
"""

import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None

_BEIJING_TZ = timezone(timedelta(hours=8))
BEIJING_TZ = ZoneInfo("Asia/Shanghai") if ZoneInfo else _BEIJING_TZ
UTC_TZ = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC_TZ)


def to_beijing(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(BEIJING_TZ)


def format_beijing(dt: datetime) -> str:
    return to_beijing(dt).strftime("%Y-%m-%d %H:%M:%S")


def isoformat_beijing(dt: datetime) -> str:
    return to_beijing(dt).isoformat()


class AuditSeverity(str, Enum):
    """审计事件严重级别"""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """审计事件类型"""
    # 用户操作
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"

    # 工作空间操作
    WORKSPACE_CREATE = "workspace.create"
    WORKSPACE_SWITCH = "workspace.switch"
    WORKSPACE_DELETE = "workspace.delete"
    WORKSPACE_EXPORT = "workspace.export"
    WORKSPACE_IMPORT = "workspace.import"

    # 本体操作
    ONTOLOGY_CREATE = "ontology.create"
    ONTOLOGY_UPDATE = "ontology.update"
    ONTOLOGY_VERSION = "ontology.version"
    ONTOLOGY_ROLLBACK = "ontology.rollback"

    # Agent 操作
    AGENT_EXECUTE = "agent.execute"
    AGENT_DECISION = "agent.decision"
    AGENT_ERROR = "agent.error"

    # Skill 操作
    SKILL_REGISTER = "skill.register"
    SKILL_EXECUTE = "skill.execute"
    SKILL_DISABLE = "skill.disable"

    # 策略操作
    POLICY_UPDATE = "policy.update"
    POLICY_EVALUATE = "policy.evaluate"
    POLICY_VIOLATION = "policy.violation"

    # 推演操作
    SIMULATION_START = "simulation.start"
    SIMULATION_COMPLETE = "simulation.complete"
    SIMULATION_ROLLBACK = "simulation.rollback"

    # 系统事件
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_CONFIG = "system.config"

    # 数据摄入
    DATA_INGEST = "data.ingest"

    # 查询
    QUERY = "query.execute"

    # 问答
    QA_ASK = "qa.ask"
    QA_FEEDBACK = "qa.feedback"

    # 反馈
    FEEDBACK_ACTION = "feedback.action"
    FEEDBACK_DECISION = "feedback.decision"


class ActorInfo(BaseModel):
    """操作者信息"""
    actor_type: str = Field(..., description="操作者类型: user | agent | system | skill")
    actor_id: str = Field(..., description="操作者标识")
    actor_name: str = Field(..., description="显示名称")
    roles: List[str] = Field(default_factory=list, description="角色")


class ResourceInfo(BaseModel):
    """目标资源"""
    resource_type: str = Field(..., description="资源类型: workspace | ontology | node | edge | policy | skill | simulation")
    resource_id: str = Field(..., description="资源标识")
    resource_name: str = Field(default="", description="资源名称")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="受影响的属性")


class ActionResult(BaseModel):
    """操作结果"""
    status: str = Field(..., description="状态: success | failure | denied")
    message: str = Field(default="", description="结果描述")
    error_code: Optional[str] = Field(None, description="错误码（失败时）")
    changes: Optional[Dict[str, Any]] = Field(None, description="变更详情（before/after）")


class AuditEvent(BaseModel):
    """审计事件 - 最小审计单元"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="事件唯一标识 (UUID)")
    timestamp: datetime = Field(default_factory=utc_now, description="事件时间戳 (UTC timezone-aware)")
    event_type: AuditEventType = Field(..., description="事件类型")
    severity: AuditSeverity = Field(default=AuditSeverity.INFO, description="严重级别")
    source: str = Field(default="system", description="事件来源")
    actor: ActorInfo = Field(..., description="操作者信息")
    action: str = Field(..., description="操作动作")
    resource: ResourceInfo = Field(..., description="目标资源")
    result: ActionResult = Field(..., description="操作结果")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    workspace_id: str = Field(default="default", description="工作空间 ID")
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="分布式追踪 ID")
    parent_event_id: Optional[str] = Field(None, description="父事件 ID（因果链）")
    duration_ms: Optional[int] = Field(None, description="操作耗时")
    checksum: Optional[str] = Field(None, description="防篡改校验")
    signature: Optional[str] = Field(None, description="数字签名")


class AuditFilter(BaseModel):
    """审计事件查询过滤器"""
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    event_types: Optional[List[AuditEventType]] = Field(None, description="事件类型列表")
    severities: Optional[List[AuditSeverity]] = Field(None, description="严重级别列表")
    actor_ids: Optional[List[str]] = Field(None, description="操作者ID列表")
    actor_types: Optional[List[str]] = Field(None, description="操作者类型列表")
    resource_types: Optional[List[str]] = Field(None, description="资源类型列表")
    resource_ids: Optional[List[str]] = Field(None, description="资源ID列表")
    workspace_id: Optional[str] = Field(None, description="工作空间ID")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    result_status: Optional[List[str]] = Field(None, description="结果状态列表")
    keyword: Optional[str] = Field(None, description="全文搜索关键词")
    limit: int = Field(default=50, description="分页大小")
    offset: int = Field(default=0, description="偏移量")
    order_by: str = Field(default="timestamp", description="排序字段")
    order_desc: bool = Field(default=True, description="降序")


class IntegrityReport(BaseModel):
    """审计日志完整性报告"""
    valid: bool = Field(..., description="是否完整")
    broken_at: Optional[str] = Field(None, description="破断点（如有）")
    total_events: int = Field(..., description="校验的事件数")


__all__ = [
    'AuditSeverity',
    'AuditEventType',
    'ActorInfo',
    'ResourceInfo',
    'ActionResult',
    'AuditEvent',
    'AuditFilter',
    'IntegrityReport'
]
