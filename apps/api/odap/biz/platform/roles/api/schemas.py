from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class RoleType(str, Enum):
    """角色类型枚举。

    约定：本枚举必须覆盖 infra.security.auth_models.GlobalRole 的全部 11 个
    全局角色（用户 JWT / menu_config role_menus 均以 global_role 字符串为键），
    另保留遗留的 DIRECTOR / INTELLIGENCE（cognition engine 与推荐引擎使用）。
    任何新增 GlobalRole 成员时必须同步补充到本枚举，保证 UI 角色下拉一致。
    """
    ADMIN = "admin"  # 全局角色：系统管理员（最高权限）
    SYSTEM_ADMIN = "system_admin"
    PROJECT_OWNER = "project_owner"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"
    GUEST = "guest"
    COMMANDER = "commander"  # 军事指挥官角色（cognition engine 使用）
    ANALYST = "analyst"
    OPERATOR = "operator"
    OBSERVER = "observer"  # 全局角色：观察者（只读）
    SCHEMA_AUDITOR = "schema_auditor"
    DIRECTOR = "director"  # 遗留角色（非全局角色，推荐引擎使用）
    INTELLIGENCE = "intelligence"  # 遗留角色（非全局角色，cognition engine 使用）

    @classmethod
    def _missing_(cls, value):
        """容错：未知角色类型一律落到 GUEST，防止新增枚举在历史数据上抛 ValueError。

        新增 SCHEMA_AUDITOR（Spec 007 Iter 1）需确保既不触发既存 switch/case
        的未处理分支，也不会对 RoleType(unknown) 构造产生运行时异常。
        """
        return cls.GUEST


# Stage H · C4 Tier3 烧账：PermissionScope 下沉到 common 叶子层（infra.opa 也需使用，
# infra→biz 违反 C4）。此处保留向后兼容再导出，内部消费者（routes/storage/tests）无需改导入。
from odap.common.permission_scope import PermissionScope  # noqa: F401


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
