"""
Mixin 领域模型 (T366)

Mixin 是可被多个 ObjectType 复用的属性集合。
对齐 AGENTS.md 规则 4/5：UUID id、List 字段用 default_factory。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class Mixin(BaseModel):
    """可复用的属性集合（Mixin 模式）"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    properties: List[str] = Field(default_factory=list)        # 复用的属性名列表
    target_type_ids: List[str] = Field(default_factory=list)   # 关联 ObjectType
    created_at: datetime = Field(default_factory=datetime.now)
