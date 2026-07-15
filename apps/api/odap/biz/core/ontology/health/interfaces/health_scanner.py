"""Data Health - HealthScanner 抽象接口 (T335)

定义健康扫描器抽象基类。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import HealthReport, HealthRule


class HealthScanner(ABC):
    """健康扫描器抽象基类"""

    @abstractmethod
    def scan(self, rule_id: Optional[str] = None) -> List[HealthReport]:
        """
        执行扫描。

        Args:
            rule_id: 仅扫描指定规则；None 时扫描所有启用的规则。

        Returns:
            生成的 HealthReport 列表。
        """
        raise NotImplementedError

    @abstractmethod
    def scan_one(self, rule: HealthRule) -> List[HealthReport]:
        """
        扫描单条规则。

        Args:
            rule: 要扫描的规则。

        Returns:
            该规则生成的 HealthReport 列表。
        """
        raise NotImplementedError


__all__ = ["HealthScanner"]
