"""USL Manager - Pydantic Schemas（API 请求/响应模型）。

全部 strict=True, extra='forbid'。
请求模型用于 body 参数校验；响应模型用于 OpenAPI 文档 + 序列化。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import DataType, HierarchyRel, SemanticType


# =====================================================================
# 通用分页响应
# =====================================================================


class UslPagedResponse(BaseModel):
    """通用分页响应基类（继承后扩展 items 字段类型）。"""

    model_config = ConfigDict(strict=True, extra="forbid")

    total: int = Field(0, ge=0, description="记录总数")
    page: int = Field(1, ge=1, description="当前页码")
    page_size: int = Field(50, ge=1, description="每页大小")


# =====================================================================
# Domain
# =====================================================================


class CreateDomainRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    code: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    en_mapping: Dict[str, str] = Field(default_factory=dict)


class UpdateDomainRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    display_name: Optional[str] = None
    description: Optional[str] = None
    en_mapping: Optional[Dict[str, str]] = None


class DomainResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    code: str
    display_name: str
    description: str = ""
    en_mapping: Dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DomainListResponse(UslPagedResponse):
    items: List[DomainResponse] = Field(default_factory=list)


# =====================================================================
# Term
# =====================================================================


class CreateTermRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    domain_id: str = Field(..., min_length=1)
    canonical: str = Field(..., min_length=1, max_length=128)
    semantic_type: SemanticType = SemanticType.OBJECT_TYPE
    synonyms: List[str] = Field(default_factory=list)
    near_synonyms: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    stoplist_flag: bool = False
    definition: str = ""

    @field_validator("semantic_type", mode="before")
    @classmethod
    def _c(cls, v):
        if type(v) is str:
            return SemanticType(v)
        return v


class UpdateTermRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    semantic_type: Optional[SemanticType] = None
    synonyms: Optional[List[str]] = None
    near_synonyms: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    stoplist_flag: Optional[bool] = None
    definition: Optional[str] = None

    @field_validator("semantic_type", mode="before")
    @classmethod
    def _c(cls, v):
        if v is None:
            return v
        if type(v) is str:
            return SemanticType(v)
        return v


class TermResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    domain_id: str
    canonical: str
    semantic_type: str
    synonyms: List[str] = Field(default_factory=list)
    near_synonyms: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    stoplist_flag: bool = False
    definition: str = ""
    created_at: str
    updated_at: str


class TermListResponse(UslPagedResponse):
    items: List[TermResponse] = Field(default_factory=list)


# =====================================================================
# Hierarchy
# =====================================================================


class CreateHierarchyRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    domain_id: str = Field(..., min_length=1)
    rel_type: HierarchyRel = HierarchyRel.IS_A
    parent_term: str = Field(..., min_length=1, max_length=128)
    child_term: str = Field(..., min_length=1, max_length=128)
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @field_validator("rel_type", mode="before")
    @classmethod
    def _c(cls, v):
        if type(v) is str:
            return HierarchyRel(v)
        return v


class UpdateHierarchyRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    rel_type: Optional[HierarchyRel] = None
    parent_term: Optional[str] = None
    child_term: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("rel_type", mode="before")
    @classmethod
    def _c(cls, v):
        if v is None:
            return v
        if type(v) is str:
            return HierarchyRel(v)
        return v


class HierarchyResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    domain_id: str
    rel_type: str
    parent_term: str
    child_term: str
    confidence: float
    created_at: str


class HierarchyListResponse(UslPagedResponse):
    items: List[HierarchyResponse] = Field(default_factory=list)


# =====================================================================
# PropertySpec
# =====================================================================


class CreatePropertySpecRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    domain_id: str = Field(..., min_length=1)
    for_term: str = Field(..., min_length=1, max_length=128)
    prop_name: str = Field(..., min_length=1, max_length=128)
    data_type: DataType = DataType.STRING
    unit: Optional[str] = None
    required_flag: bool = False
    description: str = ""

    @field_validator("data_type", mode="before")
    @classmethod
    def _c(cls, v):
        if type(v) is str:
            return DataType(v)
        return v


class UpdatePropertySpecRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    data_type: Optional[DataType] = None
    unit: Optional[str] = None
    required_flag: Optional[bool] = None
    description: Optional[str] = None

    @field_validator("data_type", mode="before")
    @classmethod
    def _c(cls, v):
        if v is None:
            return v
        if type(v) is str:
            return DataType(v)
        return v


class PropertySpecResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    domain_id: str
    for_term: str
    prop_name: str
    data_type: str
    unit: Optional[str] = None
    required_flag: bool = False
    description: str = ""


class PropertySpecListResponse(UslPagedResponse):
    items: List[PropertySpecResponse] = Field(default_factory=list)


# =====================================================================
# DisjointPair
# =====================================================================


class CreateDisjointPairRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    domain_id: str = Field(..., min_length=1)
    term_a: str = Field(..., min_length=1, max_length=128)
    term_b: str = Field(..., min_length=1, max_length=128)
    reason: str = ""


class UpdateDisjointPairRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    term_a: Optional[str] = None
    term_b: Optional[str] = None
    reason: Optional[str] = None


class DisjointPairResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    domain_id: str
    term_a: str
    term_b: str
    reason: str = ""


class DisjointPairListResponse(UslPagedResponse):
    items: List[DisjointPairResponse] = Field(default_factory=list)


# =====================================================================
# Cardinality
# =====================================================================


class CreateCardinalityRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    domain_id: str = Field(..., min_length=1)
    rel_name: str = Field(..., min_length=1, max_length=128)
    domain_term: str = Field(..., min_length=1, max_length=128)
    range_term: str = Field(..., min_length=1, max_length=128)
    min_card: int = Field(0, ge=0)
    max_card: Optional[int] = Field(default=None, gt=0)


class UpdateCardinalityRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    rel_name: Optional[str] = None
    domain_term: Optional[str] = None
    range_term: Optional[str] = None
    min_card: Optional[int] = Field(default=None, ge=0)
    max_card: Optional[int] = Field(default=None, gt=0)


class CardinalityResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    domain_id: str
    rel_name: str
    domain_term: str
    range_term: str
    min_card: int
    max_card: Optional[int] = None


class CardinalityListResponse(UslPagedResponse):
    items: List[CardinalityResponse] = Field(default_factory=list)


# =====================================================================
# Role Assignments
# =====================================================================


class WsRole(str, Enum):
    VIEWER = "viewer"
    TERM_EDITOR = "term_editor"
    DOMAIN_EDITOR = "domain_editor"
    REVIEWER = "reviewer"
    SUPER_ADMIN = "super_admin"


class AssignRoleRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    workspace_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    user_name: str = ""
    ws_role: WsRole = WsRole.VIEWER
    assigned_by: str = ""
    note: str = ""

    @field_validator("ws_role", mode="before")
    @classmethod
    def _role(cls, v):
        if v is None:
            return WsRole.VIEWER
        if isinstance(v, WsRole):
            return v
        return WsRole(str(v))


class RoleAssignmentResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    workspace_id: str
    user_id: str
    user_name: str = ""
    ws_role: str
    assigned_by: str = ""
    note: str = ""
    created_at: str
    updated_at: str


class RoleAssignmentListResponse(UslPagedResponse):
    items: List[RoleAssignmentResponse] = Field(default_factory=list)


# =====================================================================
# 通用删除响应
# =====================================================================


class DeleteResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    status: str = "ok"
    deleted: bool = True
    id: str


__all__ = [
    # Domain
    "CreateDomainRequest",
    "UpdateDomainRequest",
    "DomainResponse",
    "DomainListResponse",
    # Term
    "CreateTermRequest",
    "UpdateTermRequest",
    "TermResponse",
    "TermListResponse",
    # Hierarchy
    "CreateHierarchyRequest",
    "UpdateHierarchyRequest",
    "HierarchyResponse",
    "HierarchyListResponse",
    # PropertySpec
    "CreatePropertySpecRequest",
    "UpdatePropertySpecRequest",
    "PropertySpecResponse",
    "PropertySpecListResponse",
    # DisjointPair
    "CreateDisjointPairRequest",
    "UpdateDisjointPairRequest",
    "DisjointPairResponse",
    "DisjointPairListResponse",
    # Cardinality
    "CreateCardinalityRequest",
    "UpdateCardinalityRequest",
    "CardinalityResponse",
    "CardinalityListResponse",
    # Role
    "WsRole",
    "AssignRoleRequest",
    "RoleAssignmentResponse",
    "RoleAssignmentListResponse",
    # Common
    "DeleteResponse",
]
