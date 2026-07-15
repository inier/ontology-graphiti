"""
ResolvedProperty 值对象 — 属性链解析结果

定义在 models/ 下，避免 interfaces/ 与 impl/ 之间的循环导入。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ResolvedProperty:
    """解析后的属性来源"""
    property_name: str
    source: str                  # "self" | "parent:<type_id>" | "mixin:<mixin_id>"
    depth: int                   # 0=self, 1=最近父类, 2=上一层父类...
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_name": self.property_name,
            "source": self.source,
            "depth": self.depth,
            "value": self.value,
        }
