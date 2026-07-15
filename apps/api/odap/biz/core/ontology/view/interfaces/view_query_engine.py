"""Object View - ViewQueryEngine 抽象接口 (T406)

查询引擎处理：
- OPA 读权限校验
- 字段投影
- 过滤（eq/ne/gt/lt/in/contains 等）
- 排序
- 行限制
- 字段脱敏
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from ..models import ObjectView


@dataclass
class ViewQueryContext:
    """查询上下文（用户/工作空间/角色）"""

    user_id: str
    ws_id: str
    role: str


@dataclass
class ViewQueryResult:
    """查询结果（已脱敏、已过滤、已排序、已限制行数）"""

    rows: List[Dict[str, Any]]
    total_count: int
    truncated: bool


class ViewQueryEngine(ABC):
    """视图查询引擎抽象基类"""

    @abstractmethod
    def query(self, view: ObjectView, context: ViewQueryContext) -> ViewQueryResult:
        """
        执行视图查询。

        Args:
            view: 视图定义
            context: 用户/工作空间/角色上下文

        Returns:
            ViewQueryResult: 含 rows / total_count / truncated
        """
        raise NotImplementedError


__all__ = ["ViewQueryEngine", "ViewQueryContext", "ViewQueryResult"]
