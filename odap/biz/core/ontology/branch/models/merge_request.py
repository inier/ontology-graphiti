"""
MergeRequest 领域模型 (T349)

定义合并请求 Pydantic 模型，承载 source/target 分支、3-way 快照、冲突列表。
对齐 AGENTS.md 规则 4-5：Enum (str, Enum) 双继承，容器字段 Field(default_factory)。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MergeRequestStatus(str, Enum):
    """合并请求状态"""
    OPEN = "open"            # 刚创建
    APPROVED = "approved"    # 已审核（可选）
    MERGED = "merged"        # 已成功合并
    CONFLICT = "conflict"    # 存在未解决冲突
    CLOSED = "closed"        # 已关闭（取消）


class MergeRequest(BaseModel):
    """合并请求 (MergeRequest)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_branch_id: str                                # 源分支
    target_branch_id: str                                # 目标分支
    title: str                                           # 标题
    description: str = ""                                # 描述
    # 冲突路径 → 冲突详情（JSON 列表）
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    status: MergeRequestStatus = MergeRequestStatus.OPEN
    # 3-way 合并的三个快照
    base_snapshot: Dict[str, Any] = Field(default_factory=dict)
    ours_snapshot: Dict[str, Any] = Field(default_factory=dict)
    theirs_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    merged_at: Optional[datetime] = None
