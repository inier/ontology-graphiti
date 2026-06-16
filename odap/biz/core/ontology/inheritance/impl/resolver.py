"""
InheritanceResolver 实现 (T368)

解析 ObjectType 的完整属性链：
- self: type 自身属性
- parent:<type_id>: 父类（最近的优先，深度 1 → root 深度递增）
- mixin:<mixin_id>: Mixin 注入（优先级低于父类）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..interfaces.inheritance_repository import InheritanceRepository
from ..models.resolved_property import ResolvedProperty

logger = logging.getLogger(__name__)


SOURCE_SELF = "self"
SOURCE_PARENT = "parent"
SOURCE_MIXIN = "mixin"


class TypePropertyProvider(ABC):
    """
    抽象：提供 ObjectType 的属性定义与存在性检查。
    Service 层负责实现此接口（从 entity_types 存储查）。
    """

    @abstractmethod
    def get_property_names(self, type_id: str) -> List[str]:
        ...

    @abstractmethod
    def get_property_value(self, type_id: str, property_name: str) -> Any:
        ...


class DictTypePropertyProvider(TypePropertyProvider):
    """测试用简单实现：基于 dict 提供属性"""

    def __init__(self, type_properties: Dict[str, List[str]] = None,
                 type_values: Dict[str, Dict[str, Any]] = None):
        self._properties = type_properties or {}
        self._values = type_values or {}

    def get_property_names(self, type_id: str) -> List[str]:
        return list(self._properties.get(type_id, []))

    def get_property_value(self, type_id: str, property_name: str) -> Any:
        return self._values.get(type_id, {}).get(property_name)


class InheritanceResolver:
    """属性链解析器"""

    def __init__(
        self,
        repository: InheritanceRepository,
        property_provider: Optional[TypePropertyProvider] = None,
    ):
        self._repo = repository
        self._provider = property_provider

    def _parent_chain(self, type_id: str) -> List[str]:
        """
        沿 child→parent 边返回父类链（最近 → 最远）。
        使用迭代 + visited 防环。
        """
        visited: set = set()
        chain: List[str] = []
        current = type_id
        while True:
            if current in visited:
                break
            visited.add(current)
            edges = self._repo.list_edges(child_id=current)
            if not edges:
                break
            parent = edges[0].get("parent_type_id")
            if not parent or parent == current:
                break
            chain.append(parent)
            current = parent
        return chain

    def _resolved_for_property(
        self, type_id: str, property_name: str
    ) -> List[ResolvedProperty]:
        results: List[ResolvedProperty] = []
        if self._provider is not None:
            self_props = self._provider.get_property_names(type_id)
            if property_name in self_props:
                results.append(ResolvedProperty(
                    property_name=property_name,
                    source=SOURCE_SELF,
                    depth=0,
                    value=self._provider.get_property_value(type_id, property_name),
                ))
        parent_chain = self._parent_chain(type_id)
        for depth_idx, parent_id in enumerate(parent_chain, start=1):
            if self._provider is not None:
                parent_props = self._provider.get_property_names(parent_id)
                if property_name in parent_props:
                    results.append(ResolvedProperty(
                        property_name=property_name,
                        source=f"{SOURCE_PARENT}:{parent_id}",
                        depth=depth_idx,
                        value=self._provider.get_property_value(parent_id, property_name),
                    ))
        # Mixin: 优先级低于父类
        if self._provider is not None:
            mixins = self._repo.list_mixins_for_type(type_id)
            for mixin in mixins:
                props = mixin.get("properties", []) or []
                if property_name in props:
                    results.append(ResolvedProperty(
                        property_name=property_name,
                        source=f"{SOURCE_MIXIN}:{mixin.get('id', '')}",
                        depth=len(parent_chain) + 1,
                        value=None,
                    ))
        return results

    def resolve_property_chain(
        self, type_id: str, property_name: str
    ) -> List[ResolvedProperty]:
        """解析单个属性的来源链（self → parent → mixin）"""
        return self._resolved_for_property(type_id, property_name)

    def resolve_all_properties(
        self, type_id: str
    ) -> Dict[str, List[ResolvedProperty]]:
        """解析 ObjectType 完整属性集，按 (self+parent+mixin) 合并去重。"""
        seen: set = set()
        if self._provider is not None:
            collected: List[str] = list(self._provider.get_property_names(type_id))
            seen.update(collected)
        else:
            collected = []
        parent_chain = self._parent_chain(type_id)
        # 父类属性
        for parent_id in parent_chain:
            if self._provider is None:
                break
            for prop in self._provider.get_property_names(parent_id):
                if prop not in seen:
                    seen.add(prop)
                    collected.append(prop)
        # Mixin 属性
        for mixin in self._repo.list_mixins_for_type(type_id):
            for prop in mixin.get("properties", []) or []:
                if prop not in seen:
                    seen.add(prop)
                    collected.append(prop)
        return {p: self._resolved_for_property(type_id, p) for p in collected}


# ---------- 兼容旧函数式接口 ----------

def resolve_property_chain(
    type_id: str,
    property_name: str,
    repository: InheritanceRepository,
    property_provider: Optional[TypePropertyProvider] = None,
) -> List[ResolvedProperty]:
    resolver = InheritanceResolver(repository, property_provider)
    return resolver.resolve_property_chain(type_id, property_name)


def resolve_all_properties(
    type_id: str,
    repository: InheritanceRepository,
    property_provider: Optional[TypePropertyProvider] = None,
) -> Dict[str, List[ResolvedProperty]]:
    resolver = InheritanceResolver(repository, property_provider)
    return resolver.resolve_all_properties(type_id)
