"""审计日志便捷函数 - 共享 helper

提供统一的审计日志记录接口，消除 route 文件中的重复代码。
所有 route 模块应使用此 helper 而非各自定义 _audit() 函数。

设计要点：
- 捕获异常并记录 warning 日志（不静默吞噬，不阻断业务）
- 支持完整参数（包括 workspace_id、duration_ms）
- 统一参数命名（result_message，非 message）
- 递归保护：审计图谱写入过程中再次触发的审计会被静默丢弃，防止无限循环
"""
import logging
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger("audit_helper")

_audit_tls = threading.local()

AUDIT_ENTITY_PREFIXES = ("audit_", "user_", "resource_", "service_")
AUDIT_ENTITY_TYPES = ("AuditLog", "AuditUser", "AuditResource", "AuditService")


def _in_audit_graph_write() -> bool:
    return bool(getattr(_audit_tls, "in_graph_write", False))


def _is_audit_entity(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
) -> bool:
    if entity_type and entity_type in AUDIT_ENTITY_TYPES:
        return True
    eid = entity_id or ""
    if any(eid.startswith(p) for p in AUDIT_ENTITY_PREFIXES):
        return True
    if source_id and any(source_id.startswith(p) for p in AUDIT_ENTITY_PREFIXES):
        return True
    if target_id and any(target_id.startswith(p) for p in AUDIT_ENTITY_PREFIXES):
        return True
    return False


@contextmanager
def audit_graph_write_context():
    """审计图谱写入上下文：进入时置位，退出时还原（可嵌套）。

    用于 GraphitiAuditChannel 在写入 AuditLog 等实体时，
    防止这些图谱操作自身再次触发 graph_audit()，从而引发无限递归。
    """
    prev = getattr(_audit_tls, "in_graph_write", 0) or 0
    _audit_tls.in_graph_write = prev + 1
    try:
        yield
    finally:
        _audit_tls.in_graph_write = prev - 1 if prev > 0 else 0


def audit(
    action: str,
    user: str,
    result_status: str,
    result_message: str = "",
    details: Optional[Dict[str, Any]] = None,
    service: str = "system",
    workspace_id: str = "default",
    resource: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """审计日志便捷函数

    包装 log_audit()，捕获异常并记录警告日志，不阻断业务。

    Args:
        action: 操作名称（如 login_success, create_ontology）
        user: 操作者标识
        result_status: 结果状态 "success" | "failure" | "denied"
        result_message: 结果描述信息
        details: 附加详情（敏感字段应在调用前剔除）
        service: 服务模块名
        workspace_id: 工作空间 ID（从 JWT payload 提取，非 "default"）
        resource: 资源标识（默认使用 service 名）
        duration_ms: 操作耗时（毫秒）
    """
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource=resource or service,
            user=user,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning(
            f"Audit write failed for action={action} service={service}: {e}"
        )


def extract_user_id(user) -> str:
    """从 Depends(get_current_user) 返回的 dict 提取 user_id

    Args:
        user: get_current_user 依赖返回的用户信息 dict

    Returns:
        用户 ID 字符串，无法提取时返回 "anonymous"
    """
    if isinstance(user, dict):
        return user.get("sub", "anonymous")
    return "anonymous"


def extract_workspace_id(user) -> str:
    """从 Depends(get_current_user) 返回的 dict 提取 workspace_id

    Args:
        user: get_current_user 依赖返回的用户信息 dict

    Returns:
        工作空间 ID 字符串，无法提取时返回 "default"
    """
    if isinstance(user, dict):
        return user.get("ws_id", "default")
    return "default"


def storage_audit(
    action: str,
    *,
    result_status: str = "success",
    result_message: str = "",
    resource: str = None,
    details: Dict[str, Any] = None,
    service: str = "kb_storage",
) -> None:
    """底层存储操作审计（无用户上下文时使用，actor=system）"""
    audit(
        action=action,
        user="system",
        result_status=result_status,
        result_message=result_message,
        service=service,
        resource=resource,
        details=details or {},
    )


def graph_audit(
    action: str,
    *,
    result_status: str = "success",
    result_message: str = "",
    resource: str = None,
    details: Dict[str, Any] = None,
) -> None:
    """图谱层操作审计"""
    if _in_audit_graph_write():
        return
    if details and _is_audit_entity(
        entity_type=details.get("entity_type"),
        entity_id=details.get("entity_id"),
        source_id=details.get("source_id"),
        target_id=details.get("target_id"),
    ):
        return
    storage_audit(
        action=action,
        result_status=result_status,
        result_message=result_message,
        resource=resource,
        details=details,
        service="graph_engine",
    )


__all__ = [
    "audit",
    "extract_user_id",
    "extract_workspace_id",
    "storage_audit",
    "graph_audit",
    "audit_graph_write_context",
    "_in_audit_graph_write",
    "_is_audit_entity",
]
