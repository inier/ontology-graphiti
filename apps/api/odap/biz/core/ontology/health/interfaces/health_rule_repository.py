"""Data Health - HealthRuleRepository 抽象接口 (T334)

定义健康规则仓储的 6 个标准方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import HealthRule, HealthSeverity


class HealthRuleRepository(ABC):
    """健康规则仓储抽象基类"""

    @abstractmethod
    def save(self, rule: HealthRule) -> HealthRule:
        """保存或更新规则（upsert）"""
        raise NotImplementedError

    @abstractmethod
    def get(self, rule_id: str) -> Optional[HealthRule]:
        """根据 ID 获取规则；不存在返回 None"""
        raise NotImplementedError

    @abstractmethod
    def list(self, enabled_only: bool = False) -> List[HealthRule]:
        """列出所有规则；可仅返回 enabled"""
        raise NotImplementedError

    @abstractmethod
    def list_by_target_type(self, target_type_id: str) -> List[HealthRule]:
        """按目标实体类型 ID 过滤规则"""
        raise NotImplementedError

    @abstractmethod
    def list_by_severity(self, severity: HealthSeverity) -> List[HealthRule]:
        """按严重度过滤规则"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, rule_id: str) -> bool:
        """删除规则；返回是否成功"""
        raise NotImplementedError


__all__ = ["HealthRuleRepository"]
