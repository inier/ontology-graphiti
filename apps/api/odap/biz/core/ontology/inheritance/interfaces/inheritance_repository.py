"""
InheritanceRepository 抽象接口

定义继承边和 Mixin 的存储抽象（不与具体实现耦合）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class InheritanceRepository(ABC):
    """Inheritance + Mixin 存储抽象"""

    # ---------- edges ----------

    @abstractmethod
    def save_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_edge(self, edge_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_edge_by_pair(self, child_id: str, parent_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_edges(
        self, child_id: str = None, parent_id: str = None
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # ---------- mixins ----------

    @abstractmethod
    def save_mixin(self, mixin: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_mixin(self, mixin_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_mixin(self, mixin_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_mixins(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def attach_mixin_to_type(self, mixin_id: str, type_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def detach_mixin_from_type(self, mixin_id: str, type_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_mixins_for_type(self, type_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
