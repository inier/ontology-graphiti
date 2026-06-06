"""Object View - ObjectView 领域模型 (T403)

ObjectView 是基于某个 ObjectType 的角色视图，定义：
- projected_properties: 字段投影（白名单）
- filters: 过滤条件 JSON
- row_limit: 行数限制
- sort_order: 排序规则

对齐 AGENTS.md 规则 5 (容器字段必须 Field(default_factory=...))。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ObjectView(BaseModel):
    """角色视图定义（基于 ObjectType 投影）"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    base_type_id: str
    role: str
    projected_properties: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    row_limit: int = 100
    sort_order: List[Dict[str, str]] = Field(default_factory=list)
    enabled: bool = True
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


__all__ = ["ObjectView"]
