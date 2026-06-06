"""Object View - ViewPermission 领域模型 (T404)

ViewPermission 为特定角色绑定视图权限与字段脱敏规则。

Redaction 规则格式示例:
    {
        "$.ssn": "***-**-####",   # 自定义 pattern（# 占位符保留原字符）
        "$.email": "mask_email",  # 调用内置 mask_email 函数
        "$.salary": "REMOVE"      # 整个字段移除
    }
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field


class ViewPermission(BaseModel):
    """视图角色级权限（包含字段脱敏规则）"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    view_id: str
    role: str
    can_export: bool = False
    can_share: bool = False
    redaction_rules: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


__all__ = ["ViewPermission"]
