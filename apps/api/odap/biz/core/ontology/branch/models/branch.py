"""
Branch 领域模型 (T348)

定义本体分支 (Branch) Pydantic 模型，对齐 AGENTS.md 规则 4-5：
- Enum 必须 (str, Enum) 双继承
- 容器字段必须 Field(default_factory=...)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BranchStatus(str, Enum):
    """分支状态"""
    ACTIVE = "active"        # 活跃（可继续提交）
    MERGED = "merged"        # 已合并
    ABANDONED = "abandoned"  # 已放弃


class Branch(BaseModel):
    """本体分支 (Branch)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str                                              # 分支名
    ontology_id: str                                       # 所属本体 ID
    base_version_id: str                                   # 创建时的基线版本
    head_version_id: str                                   # 当前最新版本（HEAD）
    status: BranchStatus = BranchStatus.ACTIVE
    description: str = ""                                  # 分支说明
    created_by: str = "system"                             # 创建者
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    merged_at: Optional[datetime] = None
    merge_target_branch_id: Optional[str] = None           # 合并到的目标分支
