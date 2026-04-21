from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

router = APIRouter(prefix="/api/roles", tags=["roles"])

class RoleType(Enum):
    SYSTEM_ADMIN = "system_admin"
    PROJECT_OWNER = "project_owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"
    GUEST = "guest"

class PermissionScope(Enum):
    SYSTEM = "system"
    PROJECT = "project"
    RESOURCE = "resource"
    DATA = "data"

class Permission(BaseModel):
    id: str
    name: str
    description: str
    scope: PermissionScope
    actions: List[str]

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=200)
    role_type: RoleType
    permissions: List[str]  # 权限ID列表

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    role_type: Optional[RoleType] = None
    permissions: Optional[List[str]] = None

class Role(BaseModel):
    id: str
    name: str
    description: str
    role_type: RoleType
    permissions: List[Permission]
    created_at: datetime
    updated_at: datetime

# 模拟数据
roles_db = [
    {
        "id": "1",
        "name": "系统管理员",
        "description": "拥有系统所有权限",
        "role_type": RoleType.SYSTEM_ADMIN,
        "permissions": [
            {
                "id": "p1",
                "name": "系统管理",
                "description": "系统级管理权限",
                "scope": PermissionScope.SYSTEM,
                "actions": ["*"]
            }
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    },
    {
        "id": "2",
        "name": "项目所有者",
        "description": "项目级管理权限",
        "role_type": RoleType.PROJECT_OWNER,
        "permissions": [
            {
                "id": "p2",
                "name": "项目管理",
                "description": "项目级管理权限",
                "scope": PermissionScope.PROJECT,
                "actions": ["read", "write", "delete"]
            }
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    },
    {
        "id": "3",
        "name": "团队领导",
        "description": "团队级管理权限",
        "role_type": RoleType.TEAM_LEADER,
        "permissions": [
            {
                "id": "p3",
                "name": "团队管理",
                "description": "团队级管理权限",
                "scope": PermissionScope.PROJECT,
                "actions": ["read", "update"]
            }
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    },
    {
        "id": "4",
        "name": "成员",
        "description": "普通成员权限",
        "role_type": RoleType.MEMBER,
        "permissions": [
            {
                "id": "p4",
                "name": "资源访问",
                "description": "资源级访问权限",
                "scope": PermissionScope.RESOURCE,
                "actions": ["read"]
            }
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    },
    {
        "id": "5",
        "name": "访客",
        "description": "访客权限",
        "role_type": RoleType.GUEST,
        "permissions": [
            {
                "id": "p5",
                "name": "有限访问",
                "description": "有限的资源访问权限",
                "scope": PermissionScope.RESOURCE,
                "actions": ["limited_read"]
            }
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
]

permissions_db = [
    {
        "id": "p1",
        "name": "系统管理",
        "description": "系统级管理权限",
        "scope": PermissionScope.SYSTEM,
        "actions": ["*"]
    },
    {
        "id": "p2",
        "name": "项目管理",
        "description": "项目级管理权限",
        "scope": PermissionScope.PROJECT,
        "actions": ["read", "write", "delete"]
    },
    {
        "id": "p3",
        "name": "团队管理",
        "description": "团队级管理权限",
        "scope": PermissionScope.PROJECT,
        "actions": ["read", "update"]
    },
    {
        "id": "p4",
        "name": "资源访问",
        "description": "资源级访问权限",
        "scope": PermissionScope.RESOURCE,
        "actions": ["read"]
    },
    {
        "id": "p5",
        "name": "有限访问",
        "description": "有限的资源访问权限",
        "scope": PermissionScope.RESOURCE,
        "actions": ["limited_read"]
    }
]

@router.get("", response_model=List[Role])
async def list_roles():
    """获取角色列表"""
    return roles_db

@router.get("/{role_id}", response_model=Role)
async def get_role(role_id: str):
    """获取角色详情"""
    for role in roles_db:
        if role["id"] == role_id:
            return role
    raise HTTPException(status_code=404, detail="角色不存在")

@router.post("", response_model=Role)
async def create_role(role: RoleCreate):
    """创建角色"""
    new_role = {
        "id": str(len(roles_db) + 1),
        "name": role.name,
        "description": role.description,
        "role_type": role.role_type,
        "permissions": [p for p in permissions_db if p["id"] in role.permissions],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    roles_db.append(new_role)
    return new_role

@router.put("/{role_id}", response_model=Role)
async def update_role(role_id: str, role: RoleUpdate):
    """更新角色"""
    for i, r in enumerate(roles_db):
        if r["id"] == role_id:
            if role.name is not None:
                r["name"] = role.name
            if role.description is not None:
                r["description"] = role.description
            if role.role_type is not None:
                r["role_type"] = role.role_type
            if role.permissions is not None:
                r["permissions"] = [p for p in permissions_db if p["id"] in role.permissions]
            r["updated_at"] = datetime.now()
            return r
    raise HTTPException(status_code=404, detail="角色不存在")

@router.delete("/{role_id}")
async def delete_role(role_id: str):
    """删除角色"""
    for i, role in enumerate(roles_db):
        if role["id"] == role_id:
            roles_db.pop(i)
            return {"message": "角色删除成功"}
    raise HTTPException(status_code=404, detail="角色不存在")

@router.get("/permissions/all", response_model=List[Permission])
async def list_permissions():
    """获取所有权限"""
    return permissions_db