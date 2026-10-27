"""T1 工作空间切换（B-1，P0 前置）单元测试

背景：`/api/auth/login` 只调 `auth_service.login(u, p, ip)`，签出的 token
`ws_id` 恒为空，导致决策域全部端点 422（`get_current_workspace` fail-closed）。

本文件锁死四条契约（缺一条即不通过）：
1. 成员资格：非 admin 不得切到非成员空间（admin 可切到任一已存在空间）
2. 重签 access + refresh：只改 access 会让 15 分钟后静默回到空 `ws_id`
3. 每次切换写审计（`action=workspace_switch`）
4. 失败 403 且"不存在"与"无权限"返回同一响应体（不可枚举）
"""

import hashlib
from unittest.mock import MagicMock

import pytest


ADMIN_PASSWORD = "test-admin-password-12345"


@pytest.fixture
def shared_auth_service(monkeypatch):
    """login / switch / refresh 必须共用同一 AuthService（refresh token 存在实例内）。"""
    from odap.infra.security.auth_service import AuthService

    monkeypatch.setenv("ODAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    return AuthService()


@pytest.fixture
def client(shared_auth_service, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import odap.infra.security.auth_routes as auth_routes_module
    import odap.biz.platform.workspace.api.switch_routes as switch_module

    monkeypatch.setattr(auth_routes_module, "auth_service", shared_auth_service)
    monkeypatch.setattr(switch_module, "auth_service", shared_auth_service)

    app = FastAPI()
    app.include_router(auth_routes_module.router)
    app.include_router(switch_module.router)
    return TestClient(app)


@pytest.fixture
def access_token(client) -> str:
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _allow(*_args, **_kwargs) -> bool:
    return True


def _deny(*_args, **_kwargs) -> bool:
    return False


def _decode(token: str) -> dict:
    from odap.infra.security.jwt_service import JWTService

    return JWTService().verify_token_raw(token)


def _switch(client, token: str, workspace_id: str, checker=None):
    from odap.biz.platform.workspace.api.switch_routes import get_membership_checker

    if checker is not None:
        client.app.dependency_overrides[get_membership_checker] = lambda: checker
    try:
        return client.post(
            "/api/auth/switch-workspace",
            json={"workspace_id": workspace_id},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.app.dependency_overrides.pop(get_membership_checker, None)


# ---------------- 1. 成功切换：新 token 的 ws_id 非空 ----------------

def test_switch_workspace_signs_target_ws_id(client, access_token):
    assert _decode(access_token)["ws_id"] == ""  # 登录态本来就没有空间

    resp = _switch(client, access_token, "ws_demo", _allow)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    payload = _decode(body["access_token"])
    assert payload["ws_id"] == "ws_demo"
    assert payload["ws_role"]  # 非空，避免前端读不到角色


def test_switch_workspace_response_echoes_context(client, access_token):
    resp = _switch(client, access_token, "ws_demo", _allow)
    body = resp.json()
    assert body["ws_id"] == "ws_demo"
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0


# ---------------- 2. 成员资格 ----------------

def test_switch_workspace_non_member_forbidden(client, access_token):
    resp = _switch(client, access_token, "ws_other", _deny)
    assert resp.status_code == 403


def test_switch_workspace_unknown_ws_same_response_as_forbidden(client, access_token):
    denied = _switch(client, access_token, "ws_not_member", _deny)
    unknown = _switch(client, access_token, "ws_does_not_exist", _deny)
    assert denied.status_code == unknown.status_code == 403
    # 同一响应体：不可用该端点枚举全平台 workspace_id
    assert denied.json() == unknown.json()


def test_membership_helper_admin_allows_existing_workspace():
    from odap.biz.platform.workspace.api.switch_routes import _is_member
    from odap.biz.platform.workspace.models.workspace import Workspace, WorkspaceStatus

    ws = Workspace(name="demo", owner="someone-else", members=[], status=WorkspaceStatus.ACTIVE)
    assert _is_member(ws, "admin-id", is_admin=True) is True


def test_membership_helper_member_and_owner():
    from odap.biz.platform.workspace.api.switch_routes import _is_member
    from odap.biz.platform.workspace.models.workspace import Workspace, WorkspaceStatus

    ws = Workspace(
        name="demo", owner="owner-id", members=["member-id"], status=WorkspaceStatus.ACTIVE
    )
    assert _is_member(ws, "member-id", is_admin=False) is True
    assert _is_member(ws, "owner-id", is_admin=False) is True
    assert _is_member(ws, "stranger-id", is_admin=False) is False


def test_membership_helper_rejects_inactive_workspace():
    from odap.biz.platform.workspace.api.switch_routes import _is_member
    from odap.biz.platform.workspace.models.workspace import Workspace, WorkspaceStatus

    ws = Workspace(
        name="demo", owner="owner-id", members=["member-id"], status=WorkspaceStatus.INACTIVE
    )
    assert _is_member(ws, "member-id", is_admin=False) is False
    assert _is_member(ws, "admin-id", is_admin=True) is False


def test_membership_resolver_rejects_unknown_workspace(monkeypatch):
    import odap.biz.platform.workspace.api.switch_routes as switch_module

    monkeypatch.setattr(switch_module, "_load_workspace", lambda _ws_id: None)
    assert switch_module.resolve_workspace_membership("ws_missing", "u1", False) is False


# ---------------- 3. access 与 refresh 同时重签 ----------------

def test_switch_workspace_refresh_keeps_ws_id(client, access_token):
    switched = _switch(client, access_token, "ws_demo", _allow).json()

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": switched["refresh_token"]},
    )

    assert refreshed.status_code == 200, refreshed.text
    new_payload = _decode(refreshed.json()["access_token"])
    assert new_payload["ws_id"] == "ws_demo"  # 不会退回空 ws_id


def test_switch_workspace_registers_refresh_token(shared_auth_service, client, access_token):
    switched = _switch(client, access_token, "ws_demo", _allow).json()
    token_hash = hashlib.sha256(switched["refresh_token"].encode()).hexdigest()
    record = shared_auth_service._refresh_tokens.get(token_hash)
    assert record is not None
    assert record.workspace_id == "ws_demo"
    assert record.revoked is False


# ---------------- 4. 审计 ----------------

def test_switch_workspace_writes_audit(client, access_token, monkeypatch):
    import odap.biz.platform.workspace.api.switch_routes as switch_module

    recorder = MagicMock()
    monkeypatch.setattr(switch_module, "_audit", recorder)

    _switch(client, access_token, "ws_demo", _allow)

    assert recorder.called
    kwargs = recorder.call_args.kwargs
    assert kwargs["action"] == "workspace_switch"
    assert kwargs["result_status"] == "success"
    assert kwargs["details"]["to_ws"] == "ws_demo"


def test_switch_workspace_audits_failure(client, access_token, monkeypatch):
    import odap.biz.platform.workspace.api.switch_routes as switch_module

    recorder = MagicMock()
    monkeypatch.setattr(switch_module, "_audit", recorder)

    _switch(client, access_token, "ws_other", _deny)

    assert recorder.called
    assert recorder.call_args.kwargs["result_status"] == "failure"


# ---------------- 5. 未认证 ----------------

def test_switch_workspace_requires_token(client):
    resp = client.post("/api/auth/switch-workspace", json={"workspace_id": "ws_demo"})
    assert resp.status_code in (401, 403)


def test_switch_workspace_rejects_empty_workspace_id(client, access_token):
    resp = _switch(client, access_token, "", _allow)
    assert resp.status_code == 422
