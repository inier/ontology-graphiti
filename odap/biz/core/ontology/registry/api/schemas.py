"""TypeRegistry API 请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class RegistryObjectTypeCreate(BaseModel):
    """创建对象类型请求（需指定 ontology_id）"""
    ontology_id: str = Field(..., description="所属本体 ID")
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = ""
    description: str = ""
    properties: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Any] = Field(default_factory=list)
    primary_key: List[str] = Field(default_factory=list)
    classification_level: str = "U"
    icon: Optional[str] = None
    color: Optional[str] = None
    parent_type: Optional[str] = None


class RegistryObjectTypeUpdate(BaseModel):
    """更新对象类型请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[List[Dict[str, Any]]] = None
    links: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Any]] = None
    primary_key: Optional[List[str]] = None
    classification_level: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    parent_type: Optional[str] = None


class RegistryActionTypeCreate(BaseModel):
    """创建动作类型请求（需指定 ontology_id）"""
    ontology_id: str = Field(..., description="所属本体 ID")
    name: str = Field(..., min_length=1, max_length=100)
    target_object_type: str
    description: str = ""
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    required_roles: List[str] = Field(default_factory=list)
    confirmation_required: bool = True


class RegistryActionTypeUpdate(BaseModel):
    """更新动作类型请求"""
    name: Optional[str] = None
    target_object_type: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    required_roles: Optional[List[str]] = None
    confirmation_required: Optional[bool] = None


class RegistryLinkTypeCreate(BaseModel):
    """创建关系类型请求"""
    ontology_id: str = Field(..., description="所属本体 ID")
    name: str = Field(..., min_length=1, max_length=100)
    source_type: str
    target_type: str
    cardinality: str = "ONE_TO_MANY"
    link_type: str = "ASSOCIATION"
    is_bidirectional: bool = False
    reverse_name: Optional[str] = None
    description: str = ""


class RegistryLinkTypeUpdate(BaseModel):
    """更新关系类型请求"""
    name: Optional[str] = None
    source_type: Optional[str] = None
    target_type: Optional[str] = None
    cardinality: Optional[str] = None
    link_type: Optional[str] = None
    is_bidirectional: Optional[bool] = None
    reverse_name: Optional[str] = None
    description: Optional[str] = None


class RegistryCommitVersion(BaseModel):
    """提交 Schema 版本"""
    changelog: str = ""
