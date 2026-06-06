"""ComputedRepository 抽象接口 (T396-prep)

定义计算属性的仓储方法。实现层 (ComputedRepositoryImpl) 依赖 SQLite 持久化。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import ComputedProperty, MaterializationJob


class ComputedRepository(ABC):
    """Computed Property 仓储抽象基类"""

    # ---------- ComputedProperty CRUD ----------

    @abstractmethod
    def save_property(self, prop: ComputedProperty) -> ComputedProperty:
        """保存或更新 ComputedProperty（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get_property(self, prop_id: str) -> Optional[ComputedProperty]:
        """根据 ID 获取；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list_properties(
        self,
        target_type_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[ComputedProperty]:
        """列出 ComputedProperty；可按 target_type / enabled 过滤"""
        raise NotImplementedError

    @abstractmethod
    def delete_property(self, prop_id: str) -> bool:
        """删除 ComputedProperty；返回是否成功"""
        raise NotImplementedError

    # ---------- MaterializationJob ----------

    @abstractmethod
    def save_job(self, job: MaterializationJob) -> MaterializationJob:
        """保存 MaterializationJob（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[MaterializationJob]:
        """根据 ID 获取 MaterializationJob；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list_jobs(
        self, property_id: str, limit: int = 50
    ) -> List[MaterializationJob]:
        """列出某 ComputedProperty 的最近 N 个任务"""
        raise NotImplementedError

    # ---------- Materialized Values ----------

    @abstractmethod
    def save_materialized_value(
        self,
        property_id: str,
        instance_id: str,
        value: Any,
        computed_at_iso: str,
    ) -> None:
        """保存物化值（upsert by (property_id, instance_id)）"""
        raise NotImplementedError

    @abstractmethod
    def get_materialized_value(
        self, property_id: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取物化值；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list_materialized_values(
        self, property_id: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出某 ComputedProperty 的所有物化值"""
        raise NotImplementedError

    @abstractmethod
    def delete_materialized_values(self, property_id: str) -> int:
        """删除某 ComputedProperty 的全部物化值；返回删除条数"""
        raise NotImplementedError


__all__ = ["ComputedRepository"]
