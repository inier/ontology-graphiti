"""
Auth 数据模型 - 对齐 docs/03-modules/auth/DESIGN.md

包含:
- AuthProvider / GlobalRole 枚举
- LoginRequest / TokenPair / UserInfo
- WorkspaceMembership
- JWT Payload 类型
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
import uuid


class AuthProvider(str, Enum):
    LOCAL = "local"
    OIDC = "oidc"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"

    @classmethod
    def _missing_(cls, value):
        for member in cls:
            if member.value == str(value).lower():
                return member
        return cls.LOCAL


class GlobalRole(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    PROJECT_OWNER = "project_owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"
    GUEST = "guest"
    ADMIN = "admin"
    COMMANDER = "commander"
    ANALYST = "analyst"
    OPERATOR = "operator"
    OBSERVER = "observer"
    SCHEMA_AUDITOR = "schema_auditor"

    @classmethod
    def _missing_(cls, value):
        for member in cls:
            if member.value == str(value).lower():
                return member
        return cls.OBSERVER


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int

    @classmethod
    def from_jwt_tokens(cls, access: str, refresh: str, expires_in: int):
        return cls(access_token=access, refresh_token=refresh, expires_in=expires_in)


class WorkspaceMembership(BaseModel):
    workspace_id: str
    workspace_name: str
    role: str


class UserInfo(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    global_role: GlobalRole = GlobalRole.OBSERVER
    workspaces: list[WorkspaceMembership] = Field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict):
        return cls(
            id=payload.get("sub", ""),
            username=payload.get("name", payload.get("sub", "")),
            global_role=GlobalRole(payload.get("role", "observer")),
            workspaces=[],
        )


class JWTPayload(BaseModel):
    iss: str = "odap"
    sub: str
    exp: int
    iat: int
    role: str = "observer"
    ws_id: str = ""
    ws_role: str = ""

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


class RefreshTokenRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    token_hash: str
    workspace_id: str = ""
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revoked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class APIKeyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    key_hash: str
    prefix: str
    scopes: list[str] = Field(default_factory=list)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
