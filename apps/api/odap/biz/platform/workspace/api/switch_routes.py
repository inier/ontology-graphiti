"""工作空间切换端点（T1 / B-1，P0 前置）

`/api/auth/login` 只签出空 `ws_id` 的 token，`get_current_workspace` 又是
fail-closed（缺失即 422），结果是真实登录下决策域全部端点不可用。本端点
负责把目标工作空间写进 **access 与 refresh 两枚 token**。

三条不可退让的约束：
- 成员资格：非 admin 只能切到自己所在（或自己拥有）的空间
- 双 token 重签：只改 access 会在 15 分钟后 refresh 回空 `ws_id`
- 不可枚举：不存在与无权限返回**同一** 403 响应体

放在 biz 层而非 infra：成员关系存在 `biz.platform.workspace`，import-linter
C4 禁止 `infra -> biz`，故比架构初稿的 `infra/security/workspace_switch_routes.py`
下沉一层。
"""

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from odap.infra.security.audit_helper import audit as _audit
from odap.infra.security.auth_service import AuthService
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

auth_service = AuthService()

# 不存在与无权限共用同一文案：任何差异都会变成 workspace_id 枚举面
FORBIDDEN_DETAIL = "无权切换到该工作空间"


class SwitchWorkspaceRequest(BaseModel):
    """切换请求体（只接受空间 ID，role 一律服务端派生）。"""

    workspace_id: str = Field(..., min_length=1, max_length=64, description="目标工作空间")


def _is_member(workspace: Any, user_id: str, is_admin: bool) -> bool:
    """判定调用者是否为该空间成员（owner 视为成员；admin 视为全空间成员）。"""
    if workspace is None or not user_id:
        return False
    if getattr(workspace, "status", None) is not None:
        status_value = getattr(workspace.status, "value", workspace.status)
        if status_value != "active":
            return False
    if is_admin:
        return True
    if user_id == getattr(workspace, "owner", None):
        return True
    return user_id in (getattr(workspace, "members", None) or [])


def _load_workspace(workspace_id: str) -> Optional[Any]:
    """读取工作空间（独立函数便于测试注入，避免测试触达真实 SQLite）。"""
    from odap.biz.platform.workspace.impl.workspace import WorkspaceManager

    return WorkspaceManager().get_workspace(workspace_id)


def resolve_workspace_membership(workspace_id: str, user_id: str, is_admin: bool) -> bool:
    """默认成员资格解析：空间必须存在、处于 active 且调用者是成员。"""
    try:
        workspace = _load_workspace(workspace_id)
    except Exception as exc:  # 存储故障按无权限处理，fail-closed
        logger.warning("工作空间读取失败，按无权限处理: %s", exc)
        return False
    return _is_member(workspace, user_id, is_admin)


def get_membership_checker() -> Callable[[str, str, bool], bool]:
    """FastAPI 依赖：成员资格检查器（测试可整体替换）。"""
    return resolve_workspace_membership


def _write_audit(user: Dict[str, Any], to_ws: str, result_status: str) -> None:
    """记录切换审计；审计失败不阻断切换（audit helper 内部已吞异常）。"""
    _audit(
        action="workspace_switch",
        user=user.get("name") or user.get("sub") or "unknown",
        result_status=result_status,
        result_message="Workspace switched" if result_status == "success" else "Workspace switch denied",
        details={"from_ws": user.get("ws_id") or user.get("workspace_id") or "", "to_ws": to_ws},
        service="auth",
        workspace_id=to_ws,
        resource="workspace",
    )


def _issue_tokens(user_id: str, workspace_id: str):
    """按 user_id 重签 access + refresh；用户不存在/停用返回 None。"""
    return auth_service.issue_tokens_for_workspace(user_id, workspace_id)


def _token_response(pair: Any, workspace_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """响应体：token 对 + 目标空间上下文（前端据此更新 authStore）。"""
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": pair.token_type,
        "expires_in": pair.expires_in,
        "ws_id": workspace_id,
        "ws_role": user.get("role", ""),
    }


@router.post("/switch-workspace")
async def switch_workspace(
    body: SwitchWorkspaceRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    checker: Callable[[str, str, bool], bool] = Depends(get_membership_checker),
):
    """切换当前工作空间上下文，重签 access 与 refresh 两枚 token。"""
    user_id = user.get("sub", "")
    is_admin = user.get("role") == "admin"
    allowed = bool(user_id) and bool(checker(body.workspace_id, user_id, is_admin))
    pair = _issue_tokens(user_id, body.workspace_id) if allowed else None
    if pair is None:
        _write_audit(user, body.workspace_id, "failure")
        raise HTTPException(status_code=403, detail=FORBIDDEN_DETAIL)
    _write_audit(user, body.workspace_id, "success")
    return _token_response(pair, body.workspace_id, user)
