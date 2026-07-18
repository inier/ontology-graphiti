from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional

from .auth_service import AuthService
from .auth_models import LoginRequest, TokenPair, UserInfo, GlobalRole
from .jwt_auth import decode_token, security, get_current_user, verify_admin
from odap.infra.security.audit_helper import audit as _audit_shared


def _audit(action: str, user: str, result_status: str, result_message: str = "",
           details: dict = None, workspace_id: str = "default"):
    """认证审计便捷函数 - 固定 service=auth，使用共享 helper"""
    _audit_shared(
        action=action,
        user=user,
        result_status=result_status,
        result_message=result_message,
        details=details,
        service="auth",
        workspace_id=workspace_id,
        resource="auth",
    )


router = APIRouter(prefix="/api/auth", tags=["auth"])

auth_service = AuthService()

GLOBAL_ROLE_TO_ID = {
    "admin": "1",
    "commander": "2",
    "analyst": "3",
    "operator": "4",
    "observer": "5",
}


class RefreshRequest(BaseModel):
    refresh_token: str


class SSOCallbackRequest(BaseModel):
    provider: str
    code: str
    state: str
    redirect_uri: Optional[str] = ""


class LogoutRequest(BaseModel):
    refresh_token: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    global_role: str = "observer"


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    global_role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


@router.post("/login")
async def login(request: LoginRequest, req: Request):
    ip_address = req.client.host if req.client else ""
    result = auth_service.login(request.username, request.password, ip_address)
    if not result:
        _audit("login_failed", request.username, "failure",
               "Invalid credentials", {"client_ip": ip_address})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _audit("login_success", request.username, "success",
           "User logged in", {"client_ip": ip_address})
    user_data = auth_service._users.get(request.username, {})
    global_role = user_data.get("global_role", "")
    return {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "token_type": result.token_type,
        "expires_in": result.expires_in,
        "user": {
            "id": user_data.get("id", ""),
            "username": user_data.get("username", ""),
            "global_role": global_role,
            "role_id": GLOBAL_ROLE_TO_ID.get(global_role, "5"),
        },
    }


# 注意：/sso/providers 必须在 /sso/{provider} 之前定义，否则 FastAPI
# 会按声明顺序匹配，把 "providers" 解析为 provider_id（line 73 之前的 bug 已修）
@router.get("/sso/providers")
async def list_sso_providers():
    providers = auth_service.list_oauth2_providers()
    return {"providers": providers}


@router.get("/sso/{provider}")
async def sso_authorize(provider: str, redirect_uri: str = ""):
    result = auth_service.get_oauth2_authorize_url(provider, redirect_uri)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/sso/{provider}")
async def sso_callback(provider: str, data: SSOCallbackRequest):
    try:
        result = await auth_service.authenticate_oauth2(
            provider_id=provider,
            code=data.code,
            state=data.state,
            redirect_uri=data.redirect_uri,
        )
        if not result:
            _audit("sso_failed", "unknown", "failure",
                   f"SSO authentication failed for provider: {provider}",
                   {"provider": provider})
            raise HTTPException(status_code=401, detail="SSO认证失败")
        _audit("sso_success", "sso_user", "success",
               f"SSO login via {provider}", {"provider": provider})
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        _audit("sso_error", "unknown", "failure",
               f"SSO error: {str(e)[:200]}", {"provider": provider, "error": str(e)[:200]})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh(request: RefreshRequest):
    # 从 refresh_token 解码用户身份用于审计（不验证签名，仅提取身份）
    refresh_user = "unknown"
    try:
        payload = decode_token(request.refresh_token)
        if payload:
            refresh_user = payload.get("name") or payload.get("sub") or "unknown"
    except HTTPException:
        # decode_token 对过期/无效 token 抛 401，refresh 场景应容错：
        # refresh_token 自身可能过期，仍允许走后续 refresh 流程
        pass
    except Exception:
        pass
    result = auth_service.refresh(request.refresh_token)
    if not result:
        _audit("token_refresh_failed", refresh_user, "failure", "Invalid or expired refresh token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    _audit("token_refreshed", refresh_user, "success", "Token refreshed")
    return result.model_dump()


@router.post("/logout")
async def logout(request: LogoutRequest):
    # 从 refresh_token 解码用户身份用于审计
    logout_user = "unknown"
    try:
        payload = decode_token(request.refresh_token)
        if payload:
            logout_user = payload.get("name") or payload.get("sub") or "unknown"
    except HTTPException:
        # decode_token 对过期/无效 token 抛 401，logout 场景应容错：
        # 即使 refresh_token 已过期也应允许用户登出
        pass
    except Exception:
        pass
    success = auth_service.logout(request.refresh_token)
    if not success:
        _audit("logout_failed", logout_user, "failure", "Logout failed - token not found")
        raise HTTPException(status_code=400, detail="Logout failed")
    _audit("logout_success", logout_user, "success", "User logged out")
    return {"status": "ok", "message": "Logged out"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    global_role = user.get("role", "")
    return {
        "id": user.get("sub", ""),
        "username": user.get("name", user.get("sub", "")),
        "global_role": global_role,
        "role_id": GLOBAL_ROLE_TO_ID.get(global_role, "5"),
        "ws_id": user.get("ws_id", ""),
        "ws_role": user.get("ws_role", ""),
    }


@router.get("/users")
async def list_users(admin: dict = Depends(verify_admin)):
    users = auth_service.list_users()
    for u in users:
        u["role_id"] = GLOBAL_ROLE_TO_ID.get(u.get("global_role", ""), "5")
    return {"users": users, "total": len(users)}


@router.post("/users")
async def create_user(request: CreateUserRequest, admin: dict = Depends(verify_admin)):
    admin_user = admin.get("name", admin.get("sub", "admin"))
    try:
        role = GlobalRole(request.global_role)
    except ValueError:
        _audit("user_create_failed", admin_user, "failure",
               f"Invalid role: {request.global_role}", {"target_username": request.username})
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.global_role}")
    user = auth_service.register_user(
        username=request.username,
        password=request.password,
        email=request.email,
        role=role,
    )
    if not user:
        _audit("user_create_failed", admin_user, "failure",
               "Username already exists", {"target_username": request.username})
        raise HTTPException(status_code=409, detail="Username already exists")
    _audit("user_created", admin_user, "success",
           f"Created user {request.username} with role {request.global_role}",
           {"target_username": request.username, "target_role": request.global_role})
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "global_role": user.global_role.value,
        "role_id": GLOBAL_ROLE_TO_ID.get(user.global_role.value, "5"),
    }


@router.put("/users/{user_id}")
async def update_user(user_id: str, request: UpdateUserRequest, admin: dict = Depends(verify_admin)):
    admin_user = admin.get("name", admin.get("sub", "admin"))
    if request.global_role:
        try:
            GlobalRole(request.global_role)
        except ValueError:
            _audit("user_update_failed", admin_user, "failure",
                   f"Invalid role: {request.global_role}", {"target_user_id": user_id})
            raise HTTPException(status_code=400, detail=f"Invalid role: {request.global_role}")
    result = auth_service.update_user(
        user_id,
        email=request.email,
        global_role=request.global_role,
        is_active=request.is_active,
        password=request.password,
    )
    if not result:
        _audit("user_update_failed", admin_user, "failure",
               "User not found", {"target_user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")
    _audit("user_updated", admin_user, "success",
           f"Updated user {user_id}",
           {"target_user_id": user_id,
            "changes": {"email": request.email, "global_role": request.global_role,
                        "is_active": request.is_active, "password_changed": request.password is not None}})
    result["role_id"] = GLOBAL_ROLE_TO_ID.get(result.get("global_role", ""), "5")
    return result


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(verify_admin)):
    admin_user = admin.get("name", admin.get("sub", "admin"))
    current_user_id = admin.get("sub", "")
    if user_id == current_user_id:
        _audit("user_delete_failed", admin_user, "failure",
               "Attempted to delete self", {"target_user_id": user_id})
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    success = auth_service.delete_user(user_id)
    if not success:
        _audit("user_delete_failed", admin_user, "failure",
               "User not found", {"target_user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")
    _audit("user_deleted", admin_user, "success",
           f"Deleted user {user_id}", {"target_user_id": user_id})
    return {"status": "ok", "message": "User deleted"}
