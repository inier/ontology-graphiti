#!/usr/bin/env python3
"""
统一审计日志管理模块

提供简化的接口来使用审计日志系统。
设计要求：统一使用 Graphiti 存储作为主存储。

统一导出所有审计相关功能，包括：
- 简化接口：装饰器和便捷函数
- 核心功能：GraphitiAuditChannel 存储
- 数据模型：AuditEvent、AuditFilter 等
"""

import logging
import asyncio
import uuid
from functools import wraps
from fastapi import Request
from typing import Dict, Any, Optional, List
from datetime import datetime
from odap.infra.security.config import security_config
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
    SQLiteAuditChannel,
    get_sqlite_audit_channel
)
from odap.infra.security.audit_graphiti_channel import (
    GraphitiAuditChannel,
    get_graphiti_audit_channel
)

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

# 全局 Graphiti 审计通道实例
_graphiti_channel = None
_sqlite_channel = None


def get_graphiti_channel() -> GraphitiAuditChannel:
    """获取 Graphiti 审计通道实例"""
    global _graphiti_channel
    if _graphiti_channel is None:
        _graphiti_channel = get_graphiti_audit_channel()
    return _graphiti_channel


def get_channel() -> SQLiteAuditChannel:
    """获取 SQLite 审计通道实例（主存储）"""
    global _sqlite_channel
    if _sqlite_channel is None:
        _sqlite_channel = get_sqlite_audit_channel()
    return _sqlite_channel


def _run_sync(coro):
    """将协程同步执行"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def audit_log(action: str, resource: str = None, user: str = None, service: str = "system"):
    """
    审计日志装饰器

    同时记录到：
    1. SQLite 主存储
    2. Graphiti 辅助存储

    自动区分成功/失败：
    - 正常返回 → result_status="success"
    - 抛出异常 → result_status="failure"，记录异常信息

    用法：
    @audit_log(action="user_login", resource="auth")
    async def login(request: Request, username: str, password: str):
        pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if hasattr(arg, "client"):
                    request = arg
                    break
            if not request:
                for key, value in kwargs.items():
                    if hasattr(value, "client"):
                        request = value
                        break

            import time as _time
            start_time = _time.monotonic()

            client_ip = request.client.host if request and request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"

            try:
                result = await func(*args, **kwargs)
                duration_ms = int((_time.monotonic() - start_time) * 1000)

                logger.info(
                    f"ACTION: {action} | RESOURCE: {resource} | USER: {user} | "
                    f"IP: {client_ip} | USER_AGENT: {user_agent} | "
                    f"STATUS: SUCCESS | TIME: {duration_ms}ms"
                )

                log_audit(
                    action=action,
                    resource=resource,
                    user=user,
                    service=service,
                    result_status="success",
                    result_message="Operation completed",
                    details={
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                        "duration_ms": duration_ms
                    },
                    duration_ms=duration_ms
                )

                return result
            except Exception as e:
                duration_ms = int((_time.monotonic() - start_time) * 1000)

                # 判断是否为权限拒绝
                status = "failure"
                msg = str(e)
                if hasattr(e, 'status_code'):
                    if e.status_code in (401, 403):
                        status = "denied"

                logger.error(
                    f"ACTION: {action} | RESOURCE: {resource} | USER: {user} | "
                    f"IP: {client_ip} | USER_AGENT: {user_agent} | "
                    f"STATUS: {status.upper()} | EXCEPTION: {msg} | TIME: {duration_ms}ms"
                )

                log_audit(
                    action=action,
                    resource=resource,
                    user=user,
                    service=service,
                    result_status=status,
                    result_message=msg[:500],
                    details={
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                        "duration_ms": duration_ms,
                        "error_type": type(e).__name__,
                    },
                    duration_ms=duration_ms
                )

                raise
        return wrapper
    return decorator


def log_ingest(ingest_type: str, filename: str = None, user: str = None, service: str = "ingest"):
    """记录数据摄入日志"""
    logger.info(
        f"INGEST | TYPE: {ingest_type} | FILENAME: {filename} | USER: {user}"
    )

    log_audit(
        action="ingest_data",
        resource=ingest_type,
        user=user,
        service=service,
        details={"filename": filename, "ingest_type": ingest_type}
    )


def log_query(query: str, result_count: int, user: str = None, service: str = "query"):
    """记录查询日志"""
    logger.info(
        f"QUERY | QUERY: {query} | RESULTS: {result_count} | USER: {user}"
    )

    log_audit(
        action="query_executed",
        resource="query",
        user=user,
        service=service,
        details={"query": query, "result_count": result_count}
    )


def log_workspace(action: str, workspace_id: str, user: str = None, service: str = "workspace"):
    """记录工作空间操作日志"""
    logger.info(
        f"WORKSPACE | ACTION: {action} | ID: {workspace_id} | USER: {user}"
    )

    event_type = AuditEventType.WORKSPACE_CREATE
    if action == "delete":
        event_type = AuditEventType.WORKSPACE_DELETE
    elif action == "switch":
        event_type = AuditEventType.WORKSPACE_SWITCH

    log_audit(
        action=action,
        resource=workspace_id,
        user=user,
        service=service,
        details={"workspace_id": workspace_id}
    )


def log_error(error: str, context: str = None, user: str = None, service: str = "system"):
    """记录错误日志"""
    logger.error(
        f"ERROR | MESSAGE: {error} | CONTEXT: {context} | USER: {user}"
    )

    log_audit(
        action="error_occurred",
        resource=context or "system",
        user=user,
        service=service,
        details={"error": error}
    )


def get_stats():
    """获取审计统计信息"""
    channel = get_channel()
    return channel.get_stats()


def _infer_event_type(action: str, service: str) -> AuditEventType:
    """根据 action 和 service 推断事件类型"""
    action_lower = (action or "").lower()
    service_lower = (service or "").lower()
    is_delete = "delete" in action_lower
    is_create = "post" in action_lower or "create" in action_lower
    is_update = "put" in action_lower or "patch" in action_lower or "update" in action_lower

    if "login" in action_lower:
        return AuditEventType.USER_LOGIN
    if "logout" in action_lower:
        return AuditEventType.USER_LOGOUT
    if "auth" in service_lower or "role" in service_lower or "user" in service_lower:
        if is_delete:
            return AuditEventType.USER_LOGOUT
        return AuditEventType.USER_LOGIN
    if "ingest" in action_lower or service_lower == "ingest":
        return AuditEventType.DATA_INGEST
    if "query" in action_lower or service_lower == "query":
        return AuditEventType.QUERY
    if "workspace" in action_lower or service_lower == "workspace":
        if is_delete:
            return AuditEventType.WORKSPACE_DELETE
        if is_update or "switch" in action_lower:
            return AuditEventType.WORKSPACE_SWITCH
        return AuditEventType.WORKSPACE_CREATE
    if "ontology" in action_lower or "build" in action_lower or "pipeline" in action_lower:
        if "version" in action_lower or "pipeline" in action_lower:
            return AuditEventType.ONTOLOGY_VERSION
        if "rollback" in action_lower:
            return AuditEventType.ONTOLOGY_ROLLBACK
        return AuditEventType.ONTOLOGY_CREATE
    if "error" in action_lower:
        return AuditEventType.SYSTEM_ERROR
    if "skill" in action_lower:
        return AuditEventType.SKILL_EXECUTE
    if "agent" in action_lower:
        return AuditEventType.AGENT_EXECUTE
    if "policy" in action_lower:
        return AuditEventType.POLICY_UPDATE
    if "hook" in action_lower:
        return AuditEventType.SYSTEM_CONFIG
    if is_delete:
        return AuditEventType.SYSTEM_CONFIG
    if is_create:
        return AuditEventType.SYSTEM_CONFIG
    if is_update:
        return AuditEventType.SYSTEM_CONFIG
    return AuditEventType.SYSTEM_HEALTH


def log_audit(action: str, resource: str = None, user: str = None,
              service: str = "system", details: Dict[str, Any] = None,
              result_status: str = "success", result_message: str = "",
              severity: Optional[str] = None, workspace_id: str = "default",
              duration_ms: Optional[int] = None):
    """简化的审计日志记录 - 写入 SQLite 主存储 + Graphiti 辅助存储

    Args:
        action: 操作名称（如 login_success, create_ontology, query_executed）
        resource: 资源标识（如 /api/ontologies, workspace_id）
        user: 操作者标识
        service: 服务模块名
        details: 附加详情
        result_status: 操作结果状态 "success" | "failure" | "denied"
        result_message: 结果描述信息
        severity: 严重级别 "info" | "warn" | "error"，默认根据 result_status 推断
        workspace_id: 工作空间 ID
        duration_ms: 操作耗时（毫秒）
    """
    logger.info(
        f"AUDIT | ACTION: {action} | RESOURCE: {resource} | USER: {user} | "
        f"SERVICE: {service} | STATUS: {result_status} | MSG: {result_message}"
    )

    # 根据 result_status 推断 severity
    if severity is None:
        if result_status == "denied":
            severity = "warn"
        elif result_status == "failure":
            severity = "error"
        else:
            severity = "info"

    severity_enum = AuditSeverity(severity)

    event = AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        event_type=_infer_event_type(action, service),
        severity=severity_enum,
        source=service,
        actor={
            "actor_type": "user" if user else "system",
            "actor_id": user or "system",
            "actor_name": user or "System",
            "roles": []
        },
        action=action,
        resource={
            "resource_type": "resource",
            "resource_id": resource or "unknown",
            "resource_name": resource or "Unknown",
            "attributes": details or {}
        },
        result={
            "status": result_status,
            "message": result_message or ("Audit logged" if result_status == "success" else result_status),
        },
        context=details or {},
        workspace_id=workspace_id,
        trace_id=str(uuid.uuid4()),
        parent_event_id=None,
        duration_ms=duration_ms
    )

    try:
        sqlite_ch = get_channel()
        sqlite_ch.write_sync(event)
        sqlite_ch.flush_sync()
    except Exception as e:
        logger.warning(f"SQLite audit write failed: {e}")

    try:
        graphiti_ch = get_graphiti_channel()
        _run_sync(graphiti_ch.write(event))
    except Exception:
        pass


def audit_opa_decision(
    subject: str,
    action: str,
    resource: str,
    result: str,
    reason: str = "",
    policy_version: str = "",
    service: str = "opa",
) -> None:
    event = AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        event_type=AuditEventType.POLICY_EVALUATE,
        severity=AuditSeverity.INFO if result == "allow" else AuditSeverity.WARN,
        source=service,
        actor={
            "actor_type": "user",
            "actor_id": subject,
            "actor_name": subject,
            "roles": [],
        },
        action=action,
        resource={
            "resource_type": "policy_decision",
            "resource_id": resource,
            "resource_name": resource,
            "attributes": {
                "decision_result": result,
                "decision_reason": reason,
                "policy_version": policy_version,
            },
        },
        result={
            "status": result,
            "message": reason,
        },
        context={
            "subject": subject,
            "action": action,
            "resource": resource,
            "result": result,
            "reason": reason,
            "policy_version": policy_version,
        },
        workspace_id="default",
        trace_id=str(uuid.uuid4()),
        parent_event_id=None,
        duration_ms=None,
    )

    try:
        sqlite_ch = get_channel()
        sqlite_ch.write_sync(event)
        sqlite_ch.flush_sync()
    except Exception as e:
        logger.warning(f"OPA audit write failed: {e}")

    try:
        graphiti_ch = get_graphiti_channel()
        _run_sync(graphiti_ch.write(event))
    except Exception:
        pass


def get_audit_logs(user: str = None, service: str = None, action: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """简化的审计日志查询"""
    channel = get_channel()

    filter_obj = AuditFilter(
        limit=limit,
        offset=0,
        order_by="timestamp",
        order_desc=True
    )

    events = _run_sync(channel.query(filter_obj))

    result = []
    for event in events:
        event_dict = event.model_dump() if hasattr(event, 'model_dump') else event

        if isinstance(event_dict.get('timestamp'), datetime):
            event_dict['timestamp'] = event_dict['timestamp'].isoformat()

        if user:
            actor_id = event_dict.get('actor', {}).get('actor_id', '')
            if user not in actor_id:
                continue

        if service:
            if event_dict.get('source') != service:
                continue

        if action:
            if event_dict.get('action') != action:
                continue

        result.append(event_dict)

    return result


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
    'audit_opa_decision',

    # 数据模型
    'AuditSeverity',
    'AuditEventType',
    'ActorInfo',
    'ResourceInfo',
    'ActionResult',
    'AuditEvent',
    'AuditFilter',

    # 存储通道
    'GraphitiAuditChannel',
    'get_graphiti_audit_channel',

    # 辅助函数
    'get_graphiti_channel'
]