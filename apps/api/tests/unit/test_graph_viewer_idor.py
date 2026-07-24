"""Graph Viewer IDOR 防护测试

覆盖 P0-M1: workspace_access.assert_workspace_access 的 IDOR 校验逻辑。

测试项：
1. admin 可访问任意 workspace
2. 非 admin 只能访问自己的 workspace_id
3. workspace_id 不匹配时抛 403
4. 旧 token（无 workspace_id claim）回退到 sub 字段
5. assert_resource_owner 对 None owner_id 跳过校验（向后兼容）
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from odap.infra.security.workspace_access import (
    assert_workspace_access,
    assert_resource_owner,
)


# ============================================================
# assert_workspace_access
# ============================================================


class TestAssertWorkspaceAccess:
    """P0-M1: workspace IDOR 校验。"""

    def test_admin_can_access_any_workspace(self):
        """admin 角色可访问任意 workspace。"""
        admin_user = {"sub": "admin-1", "role": "admin", "workspace_id": "ws-admin"}
        # 不应抛异常
        assert_workspace_access(admin_user, "ws-other", action="view_nodes")

    def test_owner_can_access_own_workspace(self):
        """普通用户可访问自己的 workspace。"""
        user = {"sub": "user-A", "role": "member", "workspace_id": "ws-A"}
        assert_workspace_access(user, "ws-A", action="view_nodes")

    def test_non_owner_blocked_from_other_workspace(self):
        """普通用户访问他人 workspace 被拒绝（403）。"""
        user = {"sub": "user-A", "role": "member", "workspace_id": "ws-A"}
        with pytest.raises(HTTPException) as exc_info:
            assert_workspace_access(user, "ws-B", action="view_nodes")
        assert exc_info.value.status_code == 403

    def test_old_token_falls_back_to_sub(self):
        """旧 token 无 workspace_id claim 时，回退到 sub 字段匹配。

        这是为了兼容 P0-M1 整改前签发的 JWT。
        """
        # 无 workspace_id 字段
        old_user = {"sub": "user-legacy", "role": "member"}
        # workspace_id 参数 == sub 时允许
        assert_workspace_access(old_user, "user-legacy", action="view_nodes")

        # workspace_id 参数 != sub 时拒绝
        with pytest.raises(HTTPException) as exc_info:
            assert_workspace_access(old_user, "ws-other", action="view_nodes")
        assert exc_info.value.status_code == 403

    def test_non_dict_user_raises(self):
        """user 参数不是 dict 时抛 403（防御性）。"""
        with pytest.raises(HTTPException):
            assert_workspace_access(None, "ws-1", action="view_nodes")  # type: ignore[arg-type]


# ============================================================
# assert_resource_owner
# ============================================================


class TestAssertResourceOwner:
    """P0-M1: SSE session owner 校验。"""

    def test_owner_can_access(self):
        user = {"sub": "user-A", "role": "member"}
        assert_resource_owner(user, "user-A", resource_type="sse", resource_id="sess-1")

    def test_non_owner_blocked(self):
        user = {"sub": "user-B", "role": "member"}
        with pytest.raises(HTTPException) as exc_info:
            assert_resource_owner(user, "user-A", resource_type="sse", resource_id="sess-1")
        assert exc_info.value.status_code == 403

    def test_admin_can_access_any(self):
        user = {"sub": "admin-1", "role": "admin"}
        assert_resource_owner(user, "user-A", resource_type="sse", resource_id="sess-1")

    def test_none_owner_id_skips_check(self):
        """owner_id 为 None 时跳过校验（向后兼容旧数据）。"""
        user = {"sub": "user-B", "role": "member"}
        # owner_id=None → 不校验，不抛异常
        assert_resource_owner(user, None, resource_type="sse", resource_id="sess-1")
