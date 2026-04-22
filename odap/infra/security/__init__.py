#!/usr/bin/env python3
"""
安全模块

审计日志功能分层：
- 核心模型：audit_models.py
- 存储通道：audit_sqlite_channel.py (SQLite)、audit_graphiti_channel.py (Graphiti)
- 审计日志器：audit_logger.py (统一入口)
- 便捷接口：unified_audit.py (简化使用)
- API接口：audit_api.py (REST API)

使用方式：
    from odap.infra.security import get_audit_logger, AuditEventType, ResourceInfo

    audit_logger = get_audit_logger()
    await audit_logger.log_success(
        event_type=AuditEventType.USER_LOGIN,
        action="user_login",
        resource=ResourceInfo(resource_type="auth", resource_id="login", resource_name="Login")
    )
"""

from .config import SecurityConfig, security_config

# 尝试导入JWT模块
try:
    from .jwt_auth import decode_token, get_current_user, optional_current_user, verify_admin
except ImportError:
    decode_token = None
    get_current_user = None
    optional_current_user = None
    verify_admin = None

# 审计日志核心功能
from .audit_models import (
    AuditSeverity,
    AuditEventType,
    ActorInfo,
    ResourceInfo,
    ActionResult,
    AuditEvent,
    AuditFilter,
    IntegrityReport
)

# 存储通道
from .audit_sqlite_channel import (
    AuditChannel,
    SQLiteAuditChannel,
    get_sqlite_audit_channel,
    get_audit_channel
)

from .audit_graphiti_channel import (
    GraphitiAuditChannel,
    get_graphiti_audit_channel
)

# 审计日志器
from .audit_span import AuditSpan

from .audit_logger import (
    AuditLogger,
    get_audit_logger,
    audit_info,
    audit_warning,
    audit_error,
    audit_critical
)

# 统一审计接口
from .unified_audit import (
    audit_log,
    log_ingest,
    log_query,
    log_workspace,
    log_error,
    get_stats,
    log_audit,
    get_audit_logs
)

# API接口
from .audit_api import router as audit_router

__all__ = [
    # 安全配置和认证
    'SecurityConfig',
    'security_config',
    'decode_token',
    'get_current_user',
    'optional_current_user',
    'verify_admin',

    # 审计日志核心模型
    'AuditSeverity',
    'AuditEventType',
    'ActorInfo',
    'ResourceInfo',
    'ActionResult',
    'AuditEvent',
    'AuditFilter',
    'IntegrityReport',

    # 存储通道
    'AuditChannel',
    'SQLiteAuditChannel',
    'get_sqlite_audit_channel',
    'get_audit_channel',
    'GraphitiAuditChannel',
    'get_graphiti_audit_channel',

    # 审计日志器和跨度
    'AuditSpan',
    'AuditLogger',
    'get_audit_logger',
    'audit_info',
    'audit_warning',
    'audit_error',
    'audit_critical',

    # 统一审计接口
    'audit_log',
    'log_ingest',
    'log_query',
    'log_workspace',
    'log_error',
    'get_stats',
    'log_audit',
    'get_audit_logs',
    
    # API接口
    'audit_router'
]
