import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.platform.roles.storage.sqlite_role_storage import SQLiteRoleStorage
from odap.biz.platform.roles.api.schemas import Role, RoleType, Permission, PermissionScope, UserRoleBinding, UserRoleAssignRequest
from odap.biz.platform.roles.services.role_service import RoleService


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test_roles.db")
    return SQLiteRoleStorage(db_path=db_path)


def test_init_default_permissions(storage):
    permissions = storage.list_permissions()
    assert len(permissions) == 5


def test_init_default_roles(storage):
    roles = storage.list_roles()
    assert len(roles) == 5


def test_get_permission(storage):
    perm = storage.get_permission("p1")
    assert perm is not None
    assert perm.id == "p1"
    assert perm.name == "系统管理"
    assert perm.scope == PermissionScope.SYSTEM
    assert perm.actions == ["*"]


def test_list_permissions(storage):
    permissions = storage.list_permissions()
    assert len(permissions) == 5
    for p in permissions:
        assert isinstance(p, Permission)
        assert p.id
        assert p.name
        assert p.scope in list(PermissionScope)


def test_get_role(storage):
    role = storage.get_role("1")
    assert role is not None
    assert role.id == "1"
    assert role.name == "系统管理员"
    assert role.role_type == RoleType.SYSTEM_ADMIN
    assert len(role.permissions) == 1
    assert role.permissions[0].id == "p1"


def test_list_roles(storage):
    roles = storage.list_roles()
    assert len(roles) == 5
    for r in roles:
        assert isinstance(r, Role)
        assert r.id
        assert r.name
        assert r.role_type in list(RoleType)


def test_create_role(storage):
    role_data = {
        "name": "测试角色",
        "description": "用于测试的角色",
        "role_type": RoleType.MEMBER,
        "permissions": ["p4"]
    }
    role = storage.create_role(role_data)
    assert role is not None
    assert role.name == "测试角色"
    assert role.description == "用于测试的角色"
    assert role.role_type == RoleType.MEMBER
    assert len(role.permissions) == 1
    assert role.permissions[0].id == "p4"


def test_update_role(storage):
    updated = storage.update_role("1", {"name": "超级管理员"})
    assert updated is not None
    assert updated.name == "超级管理员"
    assert updated.role_type == RoleType.SYSTEM_ADMIN


def test_delete_role(storage):
    result = storage.delete_role("1")
    assert result is True
    assert storage.get_role("1") is None
    roles = storage.list_roles()
    assert len(roles) == 4


def test_bind_unbind_skill(storage):
    bind_result = storage.bind_skill("1", "skill_001")
    assert bind_result is True
    skills = storage.get_role_skills("1")
    assert len(skills) == 1
    assert skills[0]["skill_id"] == "skill_001"
    assert skills[0]["enabled"] is True

    unbind_result = storage.unbind_skill("1", "skill_001")
    assert unbind_result is True
    skills = storage.get_role_skills("1")
    assert len(skills) == 0


def test_bind_unbind_policy(storage):
    bind_result = storage.bind_policy("1", "policy_001", priority=10)
    assert bind_result is True
    policies = storage.get_role_policies("1")
    assert len(policies) == 1
    assert policies[0]["policy_id"] == "policy_001"
    assert policies[0]["priority"] == 10
    assert policies[0]["enabled"] is True

    unbind_result = storage.unbind_policy("1", "policy_001")
    assert unbind_result is True
    policies = storage.get_role_policies("1")
    assert len(policies) == 0


def test_get_role_skills(storage):
    storage.bind_skill("1", "skill_a", enabled=True)
    storage.bind_skill("1", "skill_b", enabled=False)
    skills = storage.get_role_skills("1")
    assert len(skills) == 2
    skill_ids = {s["skill_id"] for s in skills}
    assert skill_ids == {"skill_a", "skill_b"}


def test_get_role_policies(storage):
    storage.bind_policy("1", "policy_x", priority=5, enabled=True)
    storage.bind_policy("1", "policy_y", priority=10, enabled=False)
    policies = storage.get_role_policies("1")
    assert len(policies) == 2
    assert policies[0]["priority"] >= policies[1]["priority"]
    policy_ids = {p["policy_id"] for p in policies}
    assert policy_ids == {"policy_x", "policy_y"}


class TestUserRoleStorage:
    def test_assign_role_to_user(self, storage):
        result = storage.assign_role_to_user("1", "user_001")
        assert result is True
        roles = storage.get_user_roles("user_001")
        assert len(roles) == 1
        assert roles[0].id == "1"

    def test_assign_role_duplicate_returns_false(self, storage):
        storage.assign_role_to_user("1", "user_001")
        result = storage.assign_role_to_user("1", "user_001")
        assert result is False

    def test_assign_role_with_workspace(self, storage):
        result = storage.assign_role_to_user("1", "user_001", workspace_id="ws_1")
        assert result is True
        roles = storage.get_user_roles_in_workspace("user_001", "ws_1")
        assert len(roles) == 1
        assert roles[0].id == "1"

    def test_assign_same_role_different_workspace(self, storage):
        storage.assign_role_to_user("1", "user_001", workspace_id="ws_1")
        result = storage.assign_role_to_user("1", "user_001", workspace_id="ws_2")
        assert result is True

    def test_revoke_role_from_user(self, storage):
        storage.assign_role_to_user("1", "user_001")
        result = storage.revoke_role_from_user("1", "user_001")
        assert result is True
        roles = storage.get_user_roles("user_001")
        assert len(roles) == 0

    def test_revoke_role_not_found(self, storage):
        result = storage.revoke_role_from_user("1", "user_nonexist")
        assert result is False

    def test_revoke_role_with_workspace(self, storage):
        storage.assign_role_to_user("1", "user_001", workspace_id="ws_1")
        storage.assign_role_to_user("1", "user_001", workspace_id="ws_2")
        result = storage.revoke_role_from_user("1", "user_001", workspace_id="ws_1")
        assert result is True
        roles_ws1 = storage.get_user_roles_in_workspace("user_001", "ws_1")
        assert len(roles_ws1) == 0
        roles_ws2 = storage.get_user_roles_in_workspace("user_001", "ws_2")
        assert len(roles_ws2) == 1

    def test_get_user_roles_empty(self, storage):
        roles = storage.get_user_roles("user_nonexist")
        assert roles == []

    def test_get_user_roles_in_workspace_empty(self, storage):
        roles = storage.get_user_roles_in_workspace("user_nonexist", "ws_1")
        assert roles == []

    def test_save_role(self, storage):
        from datetime import datetime
        perm = storage.get_permission("p1")
        role = Role(
            id="custom_1",
            name="自定义角色",
            description="测试save_role",
            role_type=RoleType.MEMBER,
            permissions=[perm],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        storage.save_role(role)
        fetched = storage.get_role("custom_1")
        assert fetched is not None
        assert fetched.name == "自定义角色"

    def test_delete_role_cleans_user_roles(self, storage):
        storage.assign_role_to_user("1", "user_001")
        storage.delete_role("1")
        roles = storage.get_user_roles("user_001")
        assert len(roles) == 0


class TestUserRoleSchemas:
    def test_role_type_str_enum(self):
        assert isinstance(RoleType.SYSTEM_ADMIN, str)
        assert RoleType.SYSTEM_ADMIN == "system_admin"

    def test_permission_scope_str_enum(self):
        assert isinstance(PermissionScope.SYSTEM, str)
        assert PermissionScope.SYSTEM == "system"

    def test_user_role_binding_defaults(self):
        binding = UserRoleBinding(user_id="u1", role_id="r1")
        assert binding.workspace_id is None
        assert binding.bound_by == "system"

    def test_user_role_assign_request(self):
        req = UserRoleAssignRequest(user_id="u1", workspace_id="ws1")
        assert req.user_id == "u1"
        assert req.workspace_id == "ws1"

    def test_user_role_assign_request_no_workspace(self):
        req = UserRoleAssignRequest(user_id="u1")
        assert req.workspace_id is None


class TestRoleService:
    @pytest.fixture
    def service(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_roles.db")
        with patch.object(RoleService, '__init__', lambda self: None):
            svc = RoleService()
            svc.storage = SQLiteRoleStorage(db_path=db_path)
        return svc

    def test_assign_role_to_user(self, service):
        result = service.assign_role_to_user("1", "user_001")
        assert result["status"] == "success"

    def test_assign_role_not_found(self, service):
        result = service.assign_role_to_user("nonexist", "user_001")
        assert result["status"] == "error"

    def test_assign_role_with_workspace(self, service):
        result = service.assign_role_to_user("1", "user_001", workspace_id="ws_1", bound_by="admin")
        assert result["status"] == "success"

    def test_revoke_role_from_user(self, service):
        service.assign_role_to_user("1", "user_001")
        result = service.revoke_role_from_user("1", "user_001")
        assert result["status"] == "success"

    def test_revoke_role_not_found(self, service):
        result = service.revoke_role_from_user("1", "user_nonexist")
        assert result["status"] == "error"

    def test_revoke_role_with_workspace(self, service):
        service.assign_role_to_user("1", "user_001", workspace_id="ws_1")
        result = service.revoke_role_from_user("1", "user_001", workspace_id="ws_1")
        assert result["status"] == "success"

    def test_get_user_roles(self, service):
        service.assign_role_to_user("1", "user_001")
        roles = service.get_user_roles("user_001")
        assert isinstance(roles, list)
        assert len(roles) == 1
        assert roles[0]["id"] == "1"
        assert roles[0]["role_type"] == "system_admin"

    def test_get_user_roles_in_workspace(self, service):
        service.assign_role_to_user("1", "user_001", workspace_id="ws_1")
        roles = service.get_user_roles_in_workspace("user_001", "ws_1")
        assert len(roles) == 1

    def test_role_to_dict_permissions_serialization(self, service):
        result = service.get_role("1")
        assert "id" in result
        perms = result["permissions"]
        assert isinstance(perms, list)
        assert isinstance(perms[0], dict)
        assert "id" in perms[0]
        assert "scope" in perms[0]
        assert isinstance(perms[0]["scope"], str)

    def test_create_role(self, service):
        result = service.create_role(
            name="测试角色",
            description="测试",
            role_type=RoleType.MEMBER,
            permissions=["p4"],
        )
        assert result["name"] == "测试角色"
        assert result["role_type"] == "member"

    def test_delete_role(self, service):
        result = service.delete_role("1")
        assert result["status"] == "success"

    def test_delete_role_not_found(self, service):
        result = service.delete_role("nonexist")
        assert result["status"] == "error"
