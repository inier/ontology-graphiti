"""Action Type 领域模型 (T376)

ActionType 是面向业务用户的接口定义，包含：
- id / name / description: 基础元数据
- object_types: 适用的 ObjectType 列表
- parameters: JSON Schema 风格的参数定义
- return_type: 返回类型 ("void" | "object" | "list" | "<type_id>")
- side_effects: 副作用描述
- linked_skill_id: 委托给哪个 Skill 执行 (强制非空，确保单一事实来源)
- opa_policy_ref: OPA 策略引用
- enabled: 是否启用

对齐 AGENTS.md 规则 4 (Enum 必须 (str, Enum) 双继承) 与
规则 5 (容器字段必须 Field(default_factory=...))。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ActionType(BaseModel):
    """Action Type 业务接口定义

    业务用户面向的"接口契约"：定义一个动作长什么样、接受什么参数、产出什么。
    实际执行由 linked_skill_id 指向的 Skill 负责。
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    object_types: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    return_type: str = "void"
    side_effects: List[str] = Field(default_factory=list)
    linked_skill_id: Optional[str] = None
    opa_policy_ref: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _validate_name(self) -> "ActionType":
        """name 非空校验"""
        if not self.name or not self.name.strip():
            raise ValueError("name is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_return_type(self) -> "ActionType":
        """return_type 必须是受支持的值之一"""
        allowed = {"void", "object", "list"}
        if self.return_type not in allowed and not self.return_type:
            # 允许设置为具体 type_id (任意字符串)，仅空值拒绝
            raise ValueError("return_type cannot be empty")
        return self


__all__ = ["ActionType"]
