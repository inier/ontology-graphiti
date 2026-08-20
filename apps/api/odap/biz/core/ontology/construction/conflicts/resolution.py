"""ResolutionStrategy — 冲突消解策略库（ADR-078 §3.6）。

三种策略（吸收 Semantica）：
- ConfidenceWeightedStrategy：可信度加权（权重来自 SourceTracker）
- LatestWinsStrategy：最近优先（按 detected_at 或提供的时间戳）
- MajorityVoteStrategy：投票（多数胜出，平票取首）

resolve_conflict 便捷函数：按策略名消解单条 Conflict。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import Conflict
from .source_tracker import SourceTracker, get_source_tracker

logger = logging.getLogger(__name__)


class ResolutionStrategy(ABC):
    """消解策略抽象基类"""

    name: str = "base"

    @abstractmethod
    def resolve(self, conflict: Conflict, **kwargs) -> Dict[str, Any]:
        """消解冲突，返回 {winner: value, strategy: name, confidence: float, ...}"""


class ConfidenceWeightedStrategy(ResolutionStrategy):
    """可信度加权：按 SourceTracker 权重选最高可信度来源的值"""

    name = "confidence_weighted"

    def __init__(self, tracker: Optional[SourceTracker] = None):
        self.tracker = tracker or get_source_tracker()

    def resolve(self, conflict: Conflict, **kwargs) -> Dict[str, Any]:
        if not conflict.values or not conflict.sources:
            return {"winner": None, "strategy": self.name, "confidence": 0.0, "resolved": False}

        # 每个值关联一个来源（按索引，长度可能不一致时保守处理）
        weights = self.tracker.get_weights(conflict.sources)
        # 每个候选值取来源中最高权重
        best_value = None
        best_weight = -1.0
        for idx, value in enumerate(conflict.values):
            src = conflict.sources[idx] if idx < len(conflict.sources) else "unknown"
            w = weights.get(src, 0.5)
            if w > best_weight:
                best_weight = w
                best_value = value
        return {
            "winner": best_value,
            "strategy": self.name,
            "confidence": round(best_weight, 4),
            "resolved": best_value is not None,
        }


class LatestWinsStrategy(ResolutionStrategy):
    """最近优先：选最新的值（按 sources 顺序取最后，或按时间戳）"""

    name = "latest_wins"

    def resolve(self, conflict: Conflict, **kwargs) -> Dict[str, Any]:
        if not conflict.values:
            return {"winner": None, "strategy": self.name, "confidence": 0.0, "resolved": False}

        # 若提供 timestamps，按时间选最新；否则取 values 最后一项
        timestamps = kwargs.get("timestamps")
        if timestamps and len(timestamps) == len(conflict.values):
            idx = max(range(len(timestamps)), key=lambda i: timestamps[i])
            winner = conflict.values[idx]
        else:
            winner = conflict.values[-1]

        return {
            "winner": winner,
            "strategy": self.name,
            "confidence": 1.0,
            "resolved": True,
        }


class MajorityVoteStrategy(ResolutionStrategy):
    """投票：多数胜出，平票取首个出现"""

    name = "majority_vote"

    def resolve(self, conflict: Conflict, **kwargs) -> Dict[str, Any]:
        if not conflict.values:
            return {"winner": None, "strategy": self.name, "confidence": 0.0, "resolved": False}

        counts: Dict[Any, int] = {}
        for v in conflict.values:
            key = self._hashable(v)
            counts[key] = counts.get(key, 0) + 1

        max_count = max(counts.values())
        winners = [k for k, c in counts.items() if c == max_count]
        winner = self._unhash(winners[0])
        confidence = max_count / len(conflict.values)

        return {
            "winner": winner,
            "strategy": self.name,
            "confidence": round(confidence, 4),
            "resolved": True,
        }

    @staticmethod
    def _hashable(v):
        try:
            hash(v)
            return v
        except TypeError:
            return repr(v)

    @staticmethod
    def _unhash(v):
        return v


# 策略注册表
STRATEGIES: Dict[str, ResolutionStrategy] = {
    "confidence_weighted": ConfidenceWeightedStrategy(),
    "latest_wins": LatestWinsStrategy(),
    "majority_vote": MajorityVoteStrategy(),
}


def resolve_conflict(conflict: Conflict, strategy: str = "confidence_weighted", **kwargs) -> Dict[str, Any]:
    """按策略名消解冲突，返回消解结果并回写 conflict.resolution"""
    strat = STRATEGIES.get(strategy)
    if strat is None:
        raise ValueError(f"未知消解策略: {strategy}，可选 {list(STRATEGIES.keys())}")

    result = strat.resolve(conflict, **kwargs)
    conflict.resolution = result
    conflict.resolved = result.get("resolved", False)
    return result


__all__ = [
    "ResolutionStrategy",
    "ConfidenceWeightedStrategy",
    "LatestWinsStrategy",
    "MajorityVoteStrategy",
    "STRATEGIES",
    "resolve_conflict",
]
