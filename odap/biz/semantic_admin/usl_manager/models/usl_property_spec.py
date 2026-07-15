"""USL Property Spec - 属性规约模型。

定义某个术语（如 人物）可以携带的属性（如 姓名/阵营/出生年），
包含数据类型、单位、必填标记等。
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataType(str, Enum):
    """属性数据类型枚举。

    覆写 __str__ / __repr__ 保证 JSON 和 str() 输出均为 value。
    """

    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    JSON = "JSON"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"'{self.value}'"


class UslPropertySpec(BaseModel):
    """统一语义层 - 属性规约（某个术语可拥有哪些属性）。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = Field(..., description="所属领域 ID（外键 usl_domains.id）")
    for_term: str = Field(
        ...,
        description=(
            "属性所属的术语 canonical 名称"
            "（对应 usl_terms.canonical），如 人物"
        ),
    )
    prop_name: str = Field(..., description="属性名，如 姓名/阵营/出生年")
    data_type: DataType = Field(
        default=DataType.STRING,
        description="属性数据类型",
    )
    unit: Optional[str] = Field(
        default=None,
        description="单位（可选），如 岁/年/公里，用于 INTEGER/FLOAT 属性",
    )
    required_flag: bool = Field(
        default=False,
        description="是否为必填属性（True=必填）",
    )
    description: str = Field(
        default="",
        description="属性说明（可选）",
    )

    @field_validator("data_type", mode="before")
    @classmethod
    def _coerce_data_type(cls, v):
        # Enum 实例继承自 str → 用 type 精确判断
        if type(v) is str:
            return DataType(v)
        return v


__all__ = ["DataType", "UslPropertySpec"]
