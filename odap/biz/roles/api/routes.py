from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

from .schemas import RoleType, PermissionScope, Permission, RoleCreate, RoleUpdate, Role
from ..opa_sync import RoleOPASync

router = APIRouter(prefix="/api/roles", tags=["roles"])

from ..storage import SQLiteRoleStorage
storage = SQLiteRoleStorage()
opa_sync = RoleOPASync()

@router.get("", response_model=List[Role])
async def list_roles():
    """获取角色列表"""
    return storage.list_roles()

@router.get("/{role_id}", response_model=Role)
async def get_role(role_id: str):
    """获取角色详情"""
    role = storage.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role

@router.post("", response_model=Role)
async def create_role(role: RoleCreate):
    role_data = {
        "name": role.name,
        "description": role.description,
        "role_type": role.role_type,
        "permissions": role.permissions
    }
    created = storage.create_role(role_data)
    opa_sync.sync_role_to_opa(created.model_dump(mode='json'))
    return created

@router.put("/{role_id}", response_model=Role)
async def update_role(role_id: str, role: RoleUpdate):
    role_data = {}
    if role.name is not None:
        role_data["name"] = role.name
    if role.description is not None:
        role_data["description"] = role.description
    if role.role_type is not None:
        role_data["role_type"] = role.role_type
    if role.permissions is not None:
        role_data["permissions"] = role.permissions
    
    updated_role = storage.update_role(role_id, role_data)
    if not updated_role:
        raise HTTPException(status_code=404, detail="角色不存在")
    opa_sync.sync_role_to_opa(updated_role.model_dump(mode='json'))
    return updated_role

@router.delete("/{role_id}")
async def delete_role(role_id: str):
    success = storage.delete_role(role_id)
    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")
    opa_sync.remove_role_from_opa(role_id)
    return {"message": "角色删除成功"}

@router.get("/permissions/all", response_model=List[Permission])
async def list_permissions():
    """获取所有权限"""
    return storage.list_permissions()


class SkillBinding(BaseModel):
    skill_id: str
    enabled: bool = True

class PolicyBinding(BaseModel):
    policy_id: str
    priority: int = 0
    enabled: bool = True


@router.post("/{role_id}/skills")
async def bind_skill(role_id: str, binding: SkillBinding):
    storage.bind_skill(role_id, binding.skill_id, binding.enabled)
    return {"message": "Skill 绑定成功", "skill_id": binding.skill_id}

@router.delete("/{role_id}/skills/{skill_id}")
async def unbind_skill(role_id: str, skill_id: str):
    success = storage.unbind_skill(role_id, skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="Skill 绑定不存在")
    return {"message": "Skill 解绑成功"}

@router.get("/{role_id}/skills")
async def get_role_skills(role_id: str):
    return storage.get_role_skills(role_id)

@router.post("/{role_id}/policies")
async def bind_policy(role_id: str, binding: PolicyBinding):
    storage.bind_policy(role_id, binding.policy_id, binding.priority, binding.enabled)
    return {"message": "Policy 绑定成功", "policy_id": binding.policy_id}

@router.delete("/{role_id}/policies/{policy_id}")
async def unbind_policy(role_id: str, policy_id: str):
    success = storage.unbind_policy(role_id, policy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Policy 绑定不存在")
    return {"message": "Policy 解绑成功"}

@router.get("/{role_id}/policies")
async def get_role_policies(role_id: str):
    return storage.get_role_policies(role_id)