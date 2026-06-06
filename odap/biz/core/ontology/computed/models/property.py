"""ComputedProperty 领域模型 (T391)

计算属性：在本体 (target_type_id) 上声明的派生属性，
其值由 DSL 表达式基于其它属性 (dependencies) 计算得出。

物化策略 (MaterializationType)：
- NONE: 每次访问都重新计算
- FULL: 全量物化，一次性计算所有实例
- INCREMENTAL: 增量物化，仅在依赖属性变化时重算下游

对齐 AGENTS.md 规则 4 (Enum 必须 (str, Enum) 双继承) 与
规则 5 (容器字段必须 Field(default_factory=...))。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field, model_validator


class MaterializationType(str, Enum):
    """物化策略枚举 (str, Enum) 双继承"""
    NONE = "none"
    FULL = "full"
    INCREMENTAL = "incremental"


class ComputedProperty(BaseModel):
    """计算属性定义

    DSL 表达式示例：
    - 数学: "properties.amount * properties.quantity"
    - 字符串: "concat(properties.firstName, ' ', properties.lastName)"
    - 聚合: "sum(properties.items.amount)"
    - 条件: "if(properties.score > 60, 'pass', 'fail')"
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    target_type_id: str
    expression: str
    dependencies: List[str] = Field(default_factory=list)
    materialization: MaterializationType = MaterializationType.INCREMENTAL
    return_type: str = "any"
    description: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _validate_name(self) -> "ComputedProperty":
        """name 非空校验"""
        if not self.name or not self.name.strip():
            raise ValueError("name is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_target(self) -> "ComputedProperty":
        """target_type_id 非空校验"""
        if not self.target_type_id or not self.target_type_id.strip():
            raise ValueError("target_type_id is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_expression(self) -> "ComputedProperty":
        """expression 非空校验"""
        if not self.expression or not self.expression.strip():
            raise ValueError("expression is required and must be non-empty")
        return self


__all__ = ["ComputedProperty", "MaterializationType"]
