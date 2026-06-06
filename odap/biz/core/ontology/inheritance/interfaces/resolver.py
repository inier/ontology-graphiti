"""
InheritanceResolver 抽象接口

定义属性链解析的抽象。仅依赖 models.resolved_property，避开 impl 循环。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from ..models.resolved_property import ResolvedProperty


class InheritanceResolverInterface(ABC):
    """属性链解析器抽象"""

    @abstractmethod
    def resolve_property_chain(
        self, type_id: str, property_name: str
    ) -> List[ResolvedProperty]:
        raise NotImplementedError

    @abstractmethod
    def resolve_all_properties(
        self, type_id: str
    ) -> Dict[str, List[ResolvedProperty]]:
        raise NotImplementedError
