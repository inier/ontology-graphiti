"""审计日志便捷函数 - 共享 helper

提供统一的审计日志记录接口，消除 route 文件中的重复代码。
所有 route 模块应使用此 helper 而非各自定义 _audit() 函数。

设计要点：
- 捕获异常并记录 warning 日志（不静默吞噬，不阻断业务）
- 支持完整参数（包括 workspace_id、duration_ms）
- 统一参数命名（result_message，非 message）
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("audit_helper")


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


__all__ = ["audit", "extract_user_id", "extract_workspace_id"]
