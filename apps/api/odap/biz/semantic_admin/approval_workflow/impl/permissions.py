"""Schema Auditor 权限最小骨架（Spec 007 Iter 1）。

本模块提供 FastAPI Depends 用的 `verify_schema_auditor` 钩子。

- Iter 1/2 行为：直接从 JWT payload 中读取 `role`（全局角色）与
  `ws_role`（工作空间内角色），允许 3 全局角色写：
  {admin, schema_auditor, editor}（与 routes verify_semantic_writer 对齐），
  防止 OPA 未装好的环境报错。
- Iter 3 计划：替换为 OPA 驱动的实现，调用
  `data.semantic_admin.allow` 规则，传入 input = {role, ws_role,
  workspace_id, resource_type, action}。
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException, status

from odap.infra.security.jwt_auth import get_current_user


# 允许写的全局角色集合（与 routes.verify_semantic_writer 保持完全一致）
_SEMANTIC_WRITER_GLOBAL_ROLES: set = {"admin", "schema_auditor", "editor"}


async def verify_schema_auditor(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Depends 钩子：允许全局 admin/schema_auditor/editor 写，
    或 ws_role 具备 reviewer/domain_editor/term_editor/super_admin 之一的用户写。

    Iter 1/2 硬编码判断，确保无 OPA 环境也能运行。Iter 3 起换为 OPA
    eval（`semantic_admin.allow`）驱动。

    Raises:
        HTTPException(403): 不满足条件的调用者。

    Returns:
        当前用户 JWT payload（同 `get_current_user` 返回），供下游读取。
    """
    role = (user.get("role") or "").lower()
    ws_role = (user.get("ws_role") or "").lower()

    if role in _SEMANTIC_WRITER_GLOBAL_ROLES:
        return user

    # ws_role 域内 5 细粒度下界：viewer/term_editor/domain_editor/reviewer/super_admin
    # 其中后 4 个具备写权限
    _WS_WRITER_ROLES = {"term_editor", "domain_editor", "reviewer", "super_admin"}
    if ws_role in _WS_WRITER_ROLES:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"写操作需要全局角色 ∈ {sorted(_SEMANTIC_WRITER_GLOBAL_ROLES)} "
            f"或 ws_role ∈ {sorted(_WS_WRITER_ROLES)}，"
            f"当前 role={role!r}, ws_role={ws_role!r}"
        ),
    )
