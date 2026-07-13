from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class RoleType(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    PROJECT_OWNER = "project_owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"
    GUEST = "guest"
    DIRECTOR = "director"
    INTELLIGENCE = "intelligence"
    OPERATOR = "operator"
    ANALYST = "analyst"
    SCHEMA_AUDITOR = "schema_auditor"

    @classmethod
    def _missing_(cls, value):
        """容错：未知角色类型一律落到 GUEST，防止新增枚举在历史数据上抛 ValueError。

        新增 SCHEMA_AUDITOR（Spec 007 Iter 1）需确保既不触发既存 switch/case
        的未处理分支，也不会对 RoleType(unknown) 构造产生运行时异常。
        """
        return cls.GUEST


class PermissionScope(str, Enum):
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
    permissions: List[str]


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


class UserRoleBinding(BaseModel):
    user_id: str
    role_id: str
    workspace_id: Optional[str] = None
    bound_at: datetime = Field(default_factory=datetime.now)
    bound_by: str = "system"


class UserRoleAssignRequest(BaseModel):
    user_id: str
    workspace_id: Optional[str] = None
