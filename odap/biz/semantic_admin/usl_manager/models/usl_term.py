"""USL Term - 语义术语模型。

术语是 USL 的核心实体，规范（canonical）一个概念，并携带：
- 同义词 / 近义词 / 别名
- 停用词标记（stoplist_flag）
- 语义类型（SemanticType：对应本体 6 大类型，与质量闸 G1.3 一致）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()


class SemanticType(str, Enum):
    """语义类型枚举（6 个中文值，严格对齐质量闸 G1.3 合法集）。

    权威来源：design/04-iter3-quality-approval-design.html §② G1.3
    合法集 = {对象类型, 关系类型, 属性, 动作类型, 过程类型, 规则类型}

    覆写 __str__ / __repr__ 保证 JSON 和 str() 输出均为 value（不是 ClassName.Value）。
    """

    OBJECT_TYPE = "对象类型"
    LINK_TYPE = "关系类型"
    PROPERTY = "属性"
    ACTION_TYPE = "动作类型"
    PROCESS_TYPE = "过程类型"
    RULE_TYPE = "规则类型"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"'{self.value}'"


class UslTerm(BaseModel):
    """统一语义层 - 规范术语。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = Field(..., description="所属领域 ID（外键 usl_domains.id）")
    canonical: str = Field(..., description="规范术语名，如 势力/人物/结义")
    semantic_type: SemanticType = Field(
        default=SemanticType.OBJECT_TYPE,
        description="语义类型，6 大中文枚举，与质量闸 G1.3 对齐",
    )
    synonyms: List[str] = Field(
        default_factory=list,
        description="严格同义词列表，如 势力 的同义词 [阵营, 国家, 方]",
    )
    near_synonyms: List[str] = Field(
        default_factory=list,
        description="近义词/近义表达，如 势力 -> [军团, 集团, 诸侯]",
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="别名/简称/俗称，如 势力 -> [三国势力, 阵营]",
    )
    stoplist_flag: bool = Field(
        default=False,
        description="停用词标记：True 表示该术语不参与本体构建/查询扩展",
    )
    definition: str = Field(
        default="",
        description="术语的自然语言定义（可选）",
    )
    created_at: str = Field(
        default_factory=_utc_now_iso, description="创建时间 ISO 字符串"
    )
    updated_at: str = Field(
        default_factory=_utc_now_iso, description="更新时间 ISO 字符串"
    )

    @field_validator("semantic_type", mode="before")
    @classmethod
    def _coerce_semantic_type(cls, v):
        # 注意：Enum 实例继承自 str，因此必须用 `type(v) is str` 而非 isinstance
        if type(v) is str:
            return SemanticType(v)
        return v


__all__ = ["SemanticType", "UslTerm"]
