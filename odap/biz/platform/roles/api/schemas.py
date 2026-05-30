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
    COMMANDER = "commander"
    INTELLIGENCE = "intelligence"
    OPERATOR = "operator"
    ANALYST = "analyst"


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
