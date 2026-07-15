"""
MergeEngine 抽象基类 (T352)

3-way merge 引擎契约。算法基于 RFC 6902 JSON Patch + RFC 6901 JSON Pointer。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models import Conflict


@dataclass
class MergeResult:
    """3-way merge 结果"""
    merged: Dict[str, Any]                              # 合并后的完整文档
    conflicts: List[Conflict] = field(default_factory=list)
    auto_resolved_count: int = 0                        # 自动解决（非冲突）路径数


class MergeEngine(ABC):
    """3-way merge 引擎抽象基类"""

    @abstractmethod
    def merge(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
        source_meta: Optional[Dict[str, Any]] = None,
        target_meta: Optional[Dict[str, Any]] = None,
    ) -> MergeResult:
        """
        执行 3-way merge。

        Args:
            base: 共同祖先快照
            ours: 当前分支（source）HEAD
            theirs: 目标分支（target）HEAD
            source_meta / target_meta: 可选元数据（写入 Conflict.metadata）

        Returns:
            MergeResult: 合并结果 + 冲突列表
        """
        raise NotImplementedError

    @abstractmethod
    def detect_conflicts(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> List[Conflict]:
        """
        仅检测冲突，不返回合并结果。

        Returns:
            冲突列表（每个 Conflict.path 是 JSON Pointer）
        """
        raise NotImplementedError
