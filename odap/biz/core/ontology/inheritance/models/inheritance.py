"""
InheritanceEdge 领域模型 (T365)

表示 ObjectType 之间的继承边 (child → parent)。
对齐 AGENTS.md 规则 4/5：UUID id、容器字段用 default_factory。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field


class InheritanceEdge(BaseModel):
    """ObjectType 之间的继承边"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    child_type_id: str                # 子 ObjectType
    parent_type_id: str               # 父 ObjectType
    depth: int = 1                    # 距根节点的层级
    discriminator: Dict[str, Any] = Field(default_factory=dict)  # 区分字段
    created_at: datetime = Field(default_factory=datetime.now)
