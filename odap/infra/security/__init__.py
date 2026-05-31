#!/usr/bin/env python3
"""
安全模块

审计日志功能分层：
- 核心模型：audit_models.py
- 存储通道：audit_graphiti_channel.py (Graphiti 主存储)
- 统一接口：unified_audit.py (简化 API)

使用方式：
    from odap.infra.security import log_audit, get_audit_logs

    # 记录审计日志
    log_audit(
        action="user_login",
        resource="auth",
        user=username,
        details={"ip": client_ip, "user_agent": user_agent}
    )

    # 查询审计日志
    logs = get_audit_logs(user="admin", limit=50)
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

# 导入 audit_logger 提供向后兼容性
try:
    from .audit_logger import get_audit_logger, reset_audit_logger
except ImportError:
    get_audit_logger = None
    reset_audit_logger = None

# 审计日志核心功能（从 unified_audit 统一导出）
from .unified_audit import (
    log_audit,
    log_ingest,
    log_query,
    log_workspace,
    log_error,
    get_stats,
    get_audit_logs,
    audit_opa_decision,
    audit_log,
    GraphitiAuditChannel,
    get_graphiti_channel,
    AuditSeverity,
    AuditEventType,
    ActorInfo,
    ResourceInfo,
    ActionResult,
    AuditEvent,
    AuditFilter,
)

# API接口
try:
    from .audit_api import router as audit_router
except ImportError:
    audit_router = None

__all__ = [
    # 安全配置和认证
    'SecurityConfig',
    'security_config',
    'decode_token',
    'get_current_user',
    'optional_current_user',
    'verify_admin',

    # 审计日志统一接口
    'log_audit',
    'log_ingest',
    'log_query',
    'log_workspace',
    'log_error',
    'get_stats',
    'get_audit_logs',
    'audit_opa_decision',
    'audit_log',

    # 审计日志数据模型
    'AuditSeverity',
    'AuditEventType',
    'ActorInfo',
    'ResourceInfo',
    'ActionResult',
    'AuditEvent',
    'AuditFilter',

    # 存储通道
    'GraphitiAuditChannel',
    'get_graphiti_channel',

    # 向后兼容
    'get_audit_logger',
    'reset_audit_logger',

    # API接口
    'audit_router'
]