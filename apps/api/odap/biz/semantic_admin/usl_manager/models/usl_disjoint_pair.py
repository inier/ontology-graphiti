"""USL Disjoint Pair - 不相交术语对模型。

声明两个术语在语义上是不相交的（互斥），
例如"妖"与"神"不相交，用于消歧和冲突检测。
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class UslDisjointPair(BaseModel):
    """统一语义层 - 不相交术语对（term_a 与 term_b 语义互斥）。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = Field(..., description="所属领域 ID（外键 usl_domains.id）")
    term_a: str = Field(
        ...,
        description="术语 A canonical 名称（对应 usl_terms.canonical）",
    )
    term_b: str = Field(
        ...,
        description="术语 B canonical 名称（对应 usl_terms.canonical，与 A 互斥）",
    )
    reason: str = Field(
        default="",
        description="声明不相交的原因（可选），如 阵营划分互斥",
    )


__all__ = ["UslDisjointPair"]
