"""
冷启动领域模型 (T321)

Industry 枚举 + ColdStartReport Pydantic 模型。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Industry(str, Enum):
    """行业模板枚举（必须 (str, Enum) 双继承）"""
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    MANUFACTURING = "manufacturing"


class ColdStartReport(BaseModel):
    """冷启动引导结果报告"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    industry: Industry
    template_name: str
    template_version: str
    entity_type_count: int
    relationship_count: int
    sample_data_count: int
    loaded_at: datetime = Field(default_factory=datetime.now)
    entity_types: List[str] = Field(default_factory=list)   # 加载的实体类型名
    notes: str = ""
