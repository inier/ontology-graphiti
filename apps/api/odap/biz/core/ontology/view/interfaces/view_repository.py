"""Object View - ViewRepository 抽象接口 (T405)

定义视图与权限仓储的 9 个标准方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ObjectView, ViewPermission


class ViewRepository(ABC):
    """视图与权限仓储抽象基类"""

    # ---------- ObjectView CRUD ----------

    @abstractmethod
    def save(self, view: ObjectView) -> ObjectView:
        """保存或更新视图（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get(self, view_id: str) -> Optional[ObjectView]:
        """根据 ID 获取视图；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> List[ObjectView]:
        """列出所有视图"""
        raise NotImplementedError

    @abstractmethod
    def list_by_base_type(self, base_type_id: str) -> List[ObjectView]:
        """按 base_type_id 过滤视图"""
        raise NotImplementedError

    @abstractmethod
    def list_by_role(self, role: str) -> List[ObjectView]:
        """按角色名过滤视图"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, view_id: str) -> bool:
        """删除视图；返回是否成功"""
        raise NotImplementedError

    # ---------- ViewPermission CRUD ----------

    @abstractmethod
    def save_permission(self, perm: ViewPermission) -> ViewPermission:
        """保存或更新权限（upsert；UNIQUE(view_id, role)）"""
        raise NotImplementedError

    @abstractmethod
    def get_permissions(self, view_id: str) -> List[ViewPermission]:
        """列出视图的全部权限记录"""
        raise NotImplementedError

    @abstractmethod
    def delete_permission(self, perm_id: str) -> bool:
        """删除权限；返回是否成功"""
        raise NotImplementedError


__all__ = ["ViewRepository"]
