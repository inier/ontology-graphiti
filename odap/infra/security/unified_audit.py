#!/usr/bin/env python3
"""
统一审计日志管理模块

提供简化的接口来使用审计日志系统。
基于 AuditLogger 统一日志器，同时支持 SQLite 和 Graphiti 存储。

统一导出所有审计相关功能，包括：
- 简化接口：装饰器和便捷函数
- 核心功能：AuditLogger 和相关类
- 数据模型：AuditEvent、AuditFilter 等
"""

import logging
import asyncio
from functools import wraps
from fastapi import Request
from typing import Dict, Any, Optional, List
from datetime import datetime
from odap.infra.security.config import security_config
from odap.infra.security.audit_logger import (
    AuditLogger,
    AuditSampler,
    AuditEnricher,
    WorkspaceEnricher,
    TraceEnricher,
    get_audit_logger,
    reset_audit_logger,
    run_sync
)
from odap.infra.security.audit_models import (
    AuditEvent,
    AuditFilter,
    AuditSeverity,
    AuditEventType,
    ActorInfo,
    ResourceInfo,
    ActionResult,
    IntegrityReport
)
from odap.infra.security.audit_sqlite_channel import (
    AuditChannel,
    SQLiteAuditChannel,
    get_sqlite_audit_channel,
    get_audit_channel
)
from odap.infra.security.audit_graphiti_channel import (
    GraphitiAuditChannel,
    get_graphiti_audit_channel
)
from odap.infra.security.audit_span import AuditSpan

# 配置基础日志
logging.basicConfig(
    level=getattr(logging, security_config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(security_config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("audit")


def audit_log(action: str, resource: str = None, user: str = None, service: str = "system"):
    """
    审计日志装饰器

    同时记录到：
    1. SQLite 主存储
    2. Graphiti 补充存储

    用法：
    @audit_log(action="user_login", resource="auth")
    async def login(request: Request, username: str, password: str):
        pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            start_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
            if start_time == 0:
                start_time = asyncio.get_event_loop().time()

            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")

            try:
                result = await func(request, *args, **kwargs)
                execution_time = 0.1
                duration_ms = int(execution_time * 1000)

                logger.info(
                    f"ACTION: {action} | RESOURCE: {resource} | USER: {user} | "
                    f"IP: {client_ip} | USER_AGENT: {user_agent} | "
                    f"STATUS: SUCCESS | TIME: {execution_time:.3f}s"
                )

                audit_logger = get_audit_logger()
                await audit_logger.log_success(
                    event_type=AuditEventType.USER_LOGIN,
                    action=action,
                    resource=ResourceInfo(
                        resource_type="resource",
                        resource_id=resource or "unknown",
                        resource_name=resource or "Unknown"
                    ),
                    message="Success",
                    duration_ms=duration_ms,
                    context={
                        "client_ip": client_ip,
                        "user_agent": user_agent
                    }
                )

                return result
            except Exception as e:
                execution_time = 0.1
                duration_ms = int(execution_time * 1000)

                logger.error(
                    f"ACTION: {action} | RESOURCE: {resource} | USER: {user} | "
                    f"IP: {client_ip} | USER_AGENT: {user_agent} | "
                    f"STATUS: ERROR | EXCEPTION: {str(e)} | TIME: {execution_time:.3f}s"
                )

                audit_logger = get_audit_logger()
                await audit_logger.log_failure(
                    event_type=AuditEventType.USER_LOGIN,
                    action=action,
                    resource=ResourceInfo(
                        resource_type="resource",
                        resource_id=resource or "unknown",
                        resource_name=resource or "Unknown"
                    ),
                    message=str(e),
                    error_code=type(e).__name__,
                    duration_ms=duration_ms,
                    context={
                        "client_ip": client_ip,
                        "user_agent": user_agent
                    }
                )

                raise
        return wrapper
    return decorator


def log_ingest(ingest_type: str, filename: str = None, user: str = None, service: str = "ingest"):
    """记录数据摄入日志"""
    logger.info(
        f"INGEST | TYPE: {ingest_type} | FILENAME: {filename} | USER: {user}"
    )

    audit_logger = get_audit_logger()
    run_sync(
        audit_logger.log,
        event_type=AuditEventType.ONTOLOGY_CREATE,
        action="ingest_data",
        resource=ResourceInfo(
            resource_type="ontology",
            resource_id=ingest_type,
            resource_name=ingest_type
        ),
        result=ActionResult(status="success", message="Ingest completed"),
        context={"filename": filename, "ingest_type": ingest_type},
        source=service
    )


def log_query(query: str, result_count: int, user: str = None, service: str = "query"):
    """记录查询日志"""
    logger.info(
        f"QUERY | QUERY: {query} | RESULTS: {result_count} | USER: {user}"
    )

    audit_logger = get_audit_logger()
    run_sync(
        audit_logger.log,
        event_type=AuditEventType.ONTOLOGY_CREATE,
        action="query_executed",
        resource=ResourceInfo(
            resource_type="query",
            resource_id="query",
            resource_name="Query"
        ),
        result=ActionResult(status="success", message=f"{result_count} results"),
        context={"query": query, "result_count": result_count},
        source=service
    )


def log_workspace(action: str, workspace_id: str, user: str = None, service: str = "workspace"):
    """记录工作空间操作日志"""
    logger.info(
        f"WORKSPACE | ACTION: {action} | ID: {workspace_id} | USER: {user}"
    )

    audit_logger = get_audit_logger()

    event_type = AuditEventType.WORKSPACE_CREATE
    if action == "delete":
        event_type = AuditEventType.WORKSPACE_DELETE
    elif action == "switch":
        event_type = AuditEventType.WORKSPACE_SWITCH

    run_sync(
        audit_logger.log,
        event_type=event_type,
        action=action,
        resource=ResourceInfo(
            resource_type="workspace",
            resource_id=workspace_id,
            resource_name=f"Workspace {workspace_id}"
        ),
        result=ActionResult(status="success", message=f"Workspace {action} completed"),
        context={"workspace_id": workspace_id},
        source=service
    )


def log_error(error: str, context: str = None, user: str = None, service: str = "system"):
    """记录错误日志"""
    logger.error(
        f"ERROR | MESSAGE: {error} | CONTEXT: {context} | USER: {user}"
    )

    audit_logger = get_audit_logger()
    run_sync(
        audit_logger.log,
        event_type=AuditEventType.SYSTEM_ERROR,
        action="error_occurred",
        resource=ResourceInfo(
            resource_type="system",
            resource_id=context or "system",
            resource_name=context or "System"
        ),
        result=ActionResult(status="error", message=error),
        severity=AuditSeverity.ERROR,
        source=service
    )


def get_stats():
    """获取审计统计信息"""
    audit_logger = get_audit_logger()
    return audit_logger.get_stats()


def log_audit(action: str, resource: str = None, user: str = None, service: str = "system", details: Dict[str, Any] = None):
    """简化的审计日志记录"""
    logger.info(
        f"AUDIT | ACTION: {action} | RESOURCE: {resource} | USER: {user} | SERVICE: {service}"
    )

    audit_logger = get_audit_logger()
    return run_sync(
        audit_logger.log,
        event_type=AuditEventType.SYSTEM_HEALTH,
        action=action,
        resource=ResourceInfo(
            resource_type="resource",
            resource_id=resource or "unknown",
            resource_name=resource or "Unknown"
        ),
        result=ActionResult(status="success", message="Audit logged"),
        context=details or {},
        source=service
    )


def get_audit_logs(user: str = None, service: str = None, action: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """简化的审计日志查询"""
    filters = {}
    if user:
        filters["actor_ids"] = [user]
    if service:
        filters["source"] = service
    if action:
        filters["action"] = action

    audit_logger = get_audit_logger()
    filter_obj = AuditFilter(
        limit=limit,
        offset=0,
        order_by="timestamp",
        order_desc=True,
        **filters
    )

    events = run_sync(audit_logger.query, filter_obj)
    return [event.model_dump() if hasattr(event, 'model_dump') else event for event in events]


__all__ = [
    # 简化接口
    'audit_log',
    'log_ingest',
    'log_query',
    'log_workspace',
    'log_error',
    'get_stats',
    'log_audit',
    'get_audit_logs',
    
    # 核心功能
    'AuditLogger',
    'AuditSampler',
    'AuditEnricher',
    'WorkspaceEnricher',
    'TraceEnricher',
    'get_audit_logger',
    'reset_audit_logger',
    'run_sync',
    
    # 数据模型
    'AuditEvent',
    'AuditFilter',
    'AuditSeverity',
    'AuditEventType',
    'ActorInfo',
    'ResourceInfo',
    'ActionResult',
    'IntegrityReport',
    
    # 存储通道
    'AuditChannel',
    'SQLiteAuditChannel',
    'GraphitiAuditChannel',
    'get_audit_channel',
    'get_sqlite_audit_channel',
    'get_graphiti_audit_channel',
    
    # 审计跨度
    'AuditSpan'
]
