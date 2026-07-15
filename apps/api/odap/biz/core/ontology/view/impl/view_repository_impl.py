"""Object View - ViewRepositoryImpl (T408)

实现 ViewRepository 的 9 个抽象方法，
依赖 SQLiteViewStorage 持久化。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..interfaces import ViewRepository
from ..models import ObjectView, ViewPermission
from ..storage import SQLiteViewStorage


class ViewRepositoryImpl(ViewRepository):
    """视图与权限仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteViewStorage = None):
        self.storage = storage or SQLiteViewStorage()

    # ---------- ObjectView CRUD ----------

    def save(self, view: ObjectView) -> ObjectView:
        """保存或更新视图（upsert）"""
        view.updated_at = datetime.now()
        self.storage.save_view(self._view_to_dict(view))
        return view

    def get(self, view_id: str) -> Optional[ObjectView]:
        """根据 ID 获取视图"""
        row = self.storage.get_view(view_id)
        return self._dict_to_view(row) if row else None

    def list(self) -> List[ObjectView]:
        """列出所有视图"""
        rows = self.storage.list_views()
        return [self._dict_to_view(r) for r in rows]

    def list_by_base_type(self, base_type_id: str) -> List[ObjectView]:
        """按 base_type_id 过滤视图"""
        rows = self.storage.list_views_by_base_type(base_type_id)
        return [self._dict_to_view(r) for r in rows]

    def list_by_role(self, role: str) -> List[ObjectView]:
        """按角色名过滤视图"""
        rows = self.storage.list_views_by_role(role)
        return [self._dict_to_view(r) for r in rows]

    def delete(self, view_id: str) -> bool:
        """删除视图；返回是否成功（级联删除其权限）"""
        return self.storage.delete_view(view_id)

    # ---------- ViewPermission CRUD ----------

    def save_permission(self, perm: ViewPermission) -> ViewPermission:
        """保存或更新权限（upsert；UNIQUE(view_id, role)）"""
        self.storage.save_permission(self._perm_to_dict(perm))
        return perm

    def get_permissions(self, view_id: str) -> List[ViewPermission]:
        """列出视图的全部权限记录"""
        rows = self.storage.list_permissions(view_id)
        return [self._dict_to_perm(r) for r in rows]

    def delete_permission(self, perm_id: str) -> bool:
        """删除权限；返回是否成功"""
        return self.storage.delete_permission(perm_id)

    # ---------- 内部工具 ----------

    @staticmethod
    def _view_to_dict(view: ObjectView) -> dict:
        """ObjectView → 持久化 dict"""
        return {
            "id": view.id,
            "name": view.name,
            "description": view.description,
            "base_type_id": view.base_type_id,
            "role": view.role,
            "projected_properties": list(view.projected_properties),
            "filters": dict(view.filters),
            "row_limit": int(view.row_limit),
            "sort_order": list(view.sort_order),
            "enabled": bool(view.enabled),
            "created_by": view.created_by,
            "created_at": view.created_at.isoformat(),
            "updated_at": view.updated_at.isoformat(),
        }

    @staticmethod
    def _dict_to_view(row: dict) -> ObjectView:
        """持久化 dict → ObjectView"""
        return ObjectView(
            id=row.get("id", ""),
            name=row.get("name", ""),
            description=row.get("description", "") or "",
            base_type_id=row.get("base_type_id", ""),
            role=row.get("role", ""),
            projected_properties=row.get("projected_properties", []) or [],
            filters=row.get("filters", {}) or {},
            row_limit=int(row.get("row_limit", 100)),
            sort_order=row.get("sort_order", []) or [],
            enabled=bool(row.get("enabled", True)),
            created_by=row.get("created_by", "system"),
            created_at=_parse_dt(row.get("created_at")),
            updated_at=_parse_dt(row.get("updated_at")),
        )

    @staticmethod
    def _perm_to_dict(perm: ViewPermission) -> dict:
        """ViewPermission → 持久化 dict"""
        return {
            "id": perm.id,
            "view_id": perm.view_id,
            "role": perm.role,
            "can_export": bool(perm.can_export),
            "can_share": bool(perm.can_share),
            "redaction_rules": dict(perm.redaction_rules),
            "created_at": perm.created_at.isoformat(),
        }

    @staticmethod
    def _dict_to_perm(row: dict) -> ViewPermission:
        """持久化 dict → ViewPermission"""
        return ViewPermission(
            id=row.get("id", ""),
            view_id=row.get("view_id", ""),
            role=row.get("role", ""),
            can_export=bool(row.get("can_export", False)),
            can_share=bool(row.get("can_share", False)),
            redaction_rules=row.get("redaction_rules", {}) or {},
            created_at=_parse_dt(row.get("created_at")),
        )


def _parse_dt(value):
    """从 ISO 字符串解析 datetime；失败时回退到 now()"""
    if not value:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now()
