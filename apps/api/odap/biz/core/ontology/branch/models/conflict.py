"""
Conflict 领域模型 (T350)

定义 3-way merge 冲突记录模型：
- path: JSON Pointer (RFC 6901)，如 "/objectTypes/0/properties/2/name"
- base_value / ours_value / theirs_value: 三方值
- resolution: 解决策略
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConflictResolution(str, Enum):
    """冲突解决策略"""
    UNRESOLVED = "unresolved"   # 未解决
    USE_OURS = "use_ours"       # 保留 ours
    USE_THEIRS = "use_theirs"   # 保留 theirs
    USE_BASE = "use_base"       # 保留 base
    MANUAL = "manual"           # 人工指定 resolved_value


class Conflict(BaseModel):
    """3-way merge 冲突记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merge_request_id: str                              # 所属 MR
    path: str                                          # JSON Pointer (RFC 6901)
    base_value: Any = None                             # 基线值
    ours_value: Any = None                             # ours 值
    theirs_value: Any = None                           # theirs 值
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    resolved_value: Any = None                         # 解决后采用的值
    resolved_by: str = ""                              # 解决者
    resolved_at: Optional[datetime] = None
