"""USL Cardinality - 关系基数约束模型。

定义某个关系（rel_name）的定义域与值域以及最小/最大基数，
对应本体 link type 的 domain/range + cardinality。
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UslCardinality(BaseModel):
    """统一语义层 - 关系基数约束。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = Field(..., description="所属领域 ID（外键 usl_domains.id）")
    rel_name: str = Field(
        ...,
        description=(
            "关系名（通常为术语 canonical，如 效力于/结义），"
            "语义类型通常为 LINK_TYPE"
        ),
    )
    domain_term: str = Field(
        ...,
        description="关系定义域术语 canonical，如 效力于 的 domain 是 人物",
    )
    range_term: str = Field(
        ...,
        description="关系值域术语 canonical，如 效力于 的 range 是 势力",
    )
    min_card: int = Field(
        default=0,
        ge=0,
        description="最小出现次数，0 表示可选",
    )
    max_card: Optional[int] = Field(
        default=None,
        description="最大出现次数，None 表示无限（*）",
    )

    @field_validator("min_card")
    @classmethod
    def _check_min_card(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"min_card 必须 >= 0，收到: {v}")
        return v

    @field_validator("max_card")
    @classmethod
    def _check_max_card(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError(f"max_card 为 None 或 > 0，收到: {v}")
        return v


__all__ = ["UslCardinality"]
