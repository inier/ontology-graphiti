"""
InheritanceRepository 存储实现（基于 SQLiteInheritanceStorage）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..interfaces.inheritance_repository import InheritanceRepository
from ..storage.sqlite_inheritance_storage import SQLiteInheritanceStorage


class InheritanceRepositoryImpl(InheritanceRepository):
    def __init__(self, storage: SQLiteInheritanceStorage = None):
        self._storage = storage or SQLiteInheritanceStorage()

    # ---------- edges ----------

    def save_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.save_edge(edge)

    def delete_edge(self, edge_id: str) -> bool:
        return self._storage.delete_edge(edge_id)

    def delete_edge_by_pair(self, child_id: str, parent_id: str) -> bool:
        return self._storage.delete_edge_by_pair(child_id, parent_id)

    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_edge(edge_id)

    def list_edges(
        self, child_id: str = None, parent_id: str = None
    ) -> List[Dict[str, Any]]:
        return self._storage.list_edges(child_id=child_id, parent_id=parent_id)

    # ---------- mixins ----------

    def save_mixin(self, mixin: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.save_mixin(mixin)

    def delete_mixin(self, mixin_id: str) -> bool:
        return self._storage.delete_mixin(mixin_id)

    def get_mixin(self, mixin_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_mixin(mixin_id)

    def list_mixins(self) -> List[Dict[str, Any]]:
        return self._storage.list_mixins()

    def attach_mixin_to_type(self, mixin_id: str, type_id: str) -> bool:
        return self._storage.attach_mixin_to_type(mixin_id, type_id)

    def detach_mixin_from_type(self, mixin_id: str, type_id: str) -> bool:
        return self._storage.detach_mixin_from_type(mixin_id, type_id)

    def list_mixins_for_type(self, type_id: str) -> List[Dict[str, Any]]:
        return self._storage.list_mixins_for_type(type_id)
