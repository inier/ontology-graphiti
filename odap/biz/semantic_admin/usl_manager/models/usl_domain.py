"""USL Domain - 语义领域模型。

每个语义领域（如三国、西游）对应一个 UslDomain，
包含中英文映射、创建时间等元数据。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


class UslDomain(BaseModel):
    """统一语义层 - 领域定义。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str = Field(..., description="领域唯一编码，如 sanguo/xiyou/shared")
    display_name: str = Field(..., description="领域显示名称，如 三国演义/西游记")
    description: str = Field(default="", description="领域描述")
    en_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description='中文术语 -> 英文术语映射字典，如 {"势力": "Faction"}',
    )
    created_at: str = Field(
        default_factory=_utc_now_iso, description="创建时间 ISO 字符串"
    )
    updated_at: str = Field(
        default_factory=_utc_now_iso, description="更新时间 ISO 字符串"
    )


__all__ = ["UslDomain"]
