"""工作空间归属校验工具（P0-M1 IDOR 防护）

提供统一的 helper，用于在路由层校验调用者是否有权访问指定 workspace_id：
- admin 用户可指定任意 workspace_id（跨租户管理场景），但操作会被审计记录
- 非 admin 用户：传入的 workspace_id 必须与 JWT payload 中的 workspace_id 一致；
  若 JWT 中无 workspace_id claim（向后兼容旧 token），则 fallback 到 user["sub"]
  作为归属标识，强制数据隔离

使用示例::

    from odap.infra.security.workspace_access import assert_workspace_access

    @router.get("/nodes")
    async def get_graph_nodes(workspace_id: Optional[str] = None,
                              user=Depends(get_current_user)):
        ws = assert_workspace_access(user, workspace_id)
        entities = graph_manager.query_entities(workspace_id=ws)
        ...

设计原则：
- 校验失败抛 HTTPException(403)，由路由层透传
- 不阻断 admin 跨 workspace 管理
- 向后兼容：旧 JWT 无 workspace_id claim 时，非 admin 用户以 user_id 兜底
"""

import logging
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def assert_workspace_access(
    user: dict,
    requested_workspace_id: Optional[str],
    *,
    action: str = "access",
) -> Optional[str]:
    """校验调用者是否有权访问 requested_workspace_id，返回最终生效的 workspace_id。

    Args:
        user: JWT 解码后的 payload dict，期望含 sub/role/workspace_id 字段
        requested_workspace_id: 路由入参中的 workspace_id（可能为 None 表示不限）
        action: 审计描述（如 "graph_view" / "extraction_progress"），仅用于日志

    Returns:
        最终生效的 workspace_id（用于后续业务查询）：
        - admin + 指定 workspace_id → 返回 requested
        - admin + 未指定 → 返回 None（全量查询，admin 权限）
        - 非 admin + 指定且与归属一致 → 返回 requested
        - 非 admin + 指定但与归属不符 → 抛 403
        - 非 admin + 未指定 → 返回归属 workspace_id（强制隔离）

    Raises:
        HTTPException(403): 非 admin 用户跨 workspace 访问被拒绝
    """
    if not isinstance(user, dict):
        # 无效的 user payload（理论上是认证层 bug），保守拒绝
        logger.warning("assert_workspace_access received non-dict user payload")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication context",
        )

    role = user.get("role")
    user_workspace_id = user.get("workspace_id")
    user_sub = user.get("sub", "anonymous")

    # ── admin: 允许跨 workspace 访问 ──
    if role == "admin":
        if requested_workspace_id and requested_workspace_id != user_workspace_id:
            logger.info(
                "admin cross-workspace %s: admin=%s target_ws=%s admin_ws=%s",
                action, user_sub, requested_workspace_id, user_workspace_id,
            )
        return requested_workspace_id

    # ── 非 admin: 强制按归属隔离 ──
    # 归属 workspace_id 优先取 JWT workspace_id claim；
    # 兼容旧 token（无 workspace_id）→ fallback 到 user_sub 作为归属标识
    effective_workspace = user_workspace_id or user_sub

    if requested_workspace_id and requested_workspace_id != effective_workspace:
        logger.warning(
            "IDOR blocked: user=%s role=%s requested_ws=%s but effective_ws=%s action=%s",
            user_sub, role, requested_workspace_id, effective_workspace, action,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="跨工作空间访问被拒绝",
        )

    # 非 admin 未指定 workspace_id → 返回其归属 workspace_id（强制隔离）
    # 非 admin 指定且一致 → 返回 requested
    return requested_workspace_id or effective_workspace


def assert_resource_owner(
    user: dict,
    resource_owner_id: Optional[str],
    *,
    resource_type: str = "resource",
    resource_id: str = "",
) -> None:
    """校验调用者是否为指定资源（如 extraction session）的 owner。

    用于 SSE 进度流等场景：session_id 用户可控，但 session 内部记录了 owner_id，
    只有 owner 或 admin 可以订阅。

    Args:
        user: JWT payload
        resource_owner_id: 资源记录的 owner_id（None 表示资源未记录 owner，跳过校验）
        resource_type: 资源类型描述（审计用）
        resource_id: 资源 ID（审计用）

    Raises:
        HTTPException(403): 非 owner 且非 admin
    """
    if not isinstance(user, dict):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication context",
        )

    # 资源未记录 owner（兼容旧数据）：跳过校验，仅记 warning
    if resource_owner_id is None:
        logger.debug(
            "resource has no owner_id, skipping ownership check: type=%s id=%s",
            resource_type, resource_id,
        )
        return

    role = user.get("role")
    user_sub = user.get("sub", "anonymous")

    if role == "admin":
        return

    if user_sub != resource_owner_id:
        logger.warning(
            "IDOR blocked on %s: caller=%s owner=%s resource_id=%s",
            resource_type, user_sub, resource_owner_id, resource_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源",
        )
