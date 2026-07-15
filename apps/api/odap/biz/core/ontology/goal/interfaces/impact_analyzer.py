"""ImpactAnalyzer 抽象接口 (T420)

定义变更影响分析器的抽象方法。实现层 (ImpactAnalyzerImpl) 静态分析
JSON Patch 的 path 字段，识别受影响的 ObjectType / ActionType，
估算迁移成本与风险等级。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models import ImpactAnalysis


class ImpactAnalyzer(ABC):
    """变更影响分析器抽象基类"""

    @abstractmethod
    def analyze(
        self,
        changes: List[Dict[str, Any]],
        proposal_id: str = "",
    ) -> ImpactAnalysis:
        """分析 JSON Patch 列表，生成 ImpactAnalysis

        Args:
            changes: JSON Patch 列表 (RFC 6902)
            proposal_id: 关联的 ChangeProposal ID

        Returns:
            ImpactAnalysis: 影响分析结果
        """
        raise NotImplementedError


__all__ = ["ImpactAnalyzer"]
