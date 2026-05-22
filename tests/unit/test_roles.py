import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.roles.storage.sqlite_role_storage import SQLiteRoleStorage
from odap.biz.roles.api.schemas import Role, RoleType, Permission, PermissionScope


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
