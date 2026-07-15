"""
Inheritance API Schemas (T371)

请求/响应 Pydantic 模型。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AddEdgeRequest(BaseModel):
    child_type_id: str
    parent_type_id: str
    discriminator: Dict[str, Any] = Field(default_factory=dict)


class CreateMixinRequest(BaseModel):
    name: str
    description: str = ""
    properties: List[str] = Field(default_factory=list)
    target_type_ids: List[str] = Field(default_factory=list)


class UpdateMixinRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[List[str]] = None
    target_type_ids: Optional[List[str]] = None


class ValidateRequest(BaseModel):
    type_id: str
