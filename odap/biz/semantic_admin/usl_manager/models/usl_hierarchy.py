"""USL Hierarchy - 术语层级关系模型。

描述术语之间的 IS_A（继承）、PART_OF（部分）、INSTANCE_OF（实例）层级关系，
支持置信度（confidence 0~1）用于区分人工确认 / 自动抽取。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


class HierarchyRel(str, Enum):
    """层级关系类型枚举。

    覆写 __str__ / __repr__ 保证 JSON 和 str() 输出均为 value。
    """

    IS_A = "IS_A"  # 继承 / 泛化（如 武将 IS_A 人物）
    PART_OF = "PART_OF"  # 部分 / 组成（如 心脏 PART_OF 人体）
    INSTANCE_OF = "INSTANCE_OF"  # 实例（如 刘备 INSTANCE_OF 人物）

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"'{self.value}'"


class UslHierarchy(BaseModel):
    """统一语义层 - 术语层级关系。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = Field(..., description="所属领域 ID（外键 usl_domains.id）")
    rel_type: HierarchyRel = Field(
        default=HierarchyRel.IS_A,
        description="层级关系类型：IS_A / PART_OF / INSTANCE_OF",
    )
    parent_term: str = Field(
        ...,
        description="父术语 canonical 名称（对应 usl_terms.canonical）",
    )
    child_term: str = Field(
        ...,
        description="子术语 canonical 名称（对应 usl_terms.canonical）",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="置信度 0~1：1.0 表示人工确认，<1.0 表示自动抽取",
    )
    created_at: str = Field(
        default_factory=_utc_now_iso, description="创建时间 ISO 字符串"
    )

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence 必须在 [0, 1] 区间，收到: {v}")
        return v

    @field_validator("rel_type", mode="before")
    @classmethod
    def _coerce_rel_type(cls, v):
        # Enum 实例继承自 str → 用 type 精确判断
        if type(v) is str:
            return HierarchyRel(v)
        return v


__all__ = ["HierarchyRel", "UslHierarchy"]
