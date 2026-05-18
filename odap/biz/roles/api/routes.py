from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

from .schemas import RoleType, PermissionScope, Permission, RoleCreate, RoleUpdate, Role

router = APIRouter(prefix="/api/roles", tags=["roles"])

# 使用SQLite存储
from ..storage import SQLiteRoleStorage
storage = SQLiteRoleStorage()

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
    """创建角色"""
    role_data = {
        "name": role.name,
        "description": role.description,
        "role_type": role.role_type,
        "permissions": role.permissions
    }
    return storage.create_role(role_data)

@router.put("/{role_id}", response_model=Role)
async def update_role(role_id: str, role: RoleUpdate):
    """更新角色"""
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
    return updated_role

@router.delete("/{role_id}")
async def delete_role(role_id: str):
    """删除角色"""
    success = storage.delete_role(role_id)
    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"message": "角色删除成功"}

@router.get("/permissions/all", response_model=List[Permission])
async def list_permissions():
    """获取所有权限"""
    return storage.list_permissions()