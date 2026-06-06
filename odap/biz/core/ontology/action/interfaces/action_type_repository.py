"""ActionTypeRepository 抽象接口 (T378)

定义 ActionType 与 ActionExecution 的仓储方法。
仓储实现 (ActionTypeRepositoryImpl) 依赖 SQLite 持久化。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ActionExecution, ActionType


class ActionTypeRepository(ABC):
    """Action Type 仓储抽象基类"""

    # ---------- ActionType CRUD ----------

    @abstractmethod
    def save(self, action_type: ActionType) -> ActionType:
        """保存或更新 ActionType（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get(self, action_type_id: str) -> Optional[ActionType]:
        """根据 ID 获取 ActionType；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list(self, enabled_only: bool = False) -> List[ActionType]:
        """列出 ActionType；可仅返回 enabled"""
        raise NotImplementedError

    @abstractmethod
    def list_by_object_type(self, type_id: str) -> List[ActionType]:
        """按适用 ObjectType 过滤 ActionType"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, action_type_id: str) -> bool:
        """删除 ActionType；返回是否成功"""
        raise NotImplementedError

    # ---------- ActionExecution ----------

    @abstractmethod
    def save_execution(self, execution: ActionExecution) -> ActionExecution:
        """保存 ActionExecution（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        """根据 ID 获取 ActionExecution"""
        raise NotImplementedError

    @abstractmethod
    def list_executions(self, action_type_id: str, limit: int = 50) -> List[ActionExecution]:
        """列出某 ActionType 的最近 N 次执行"""
        raise NotImplementedError


__all__ = ["ActionTypeRepository"]
