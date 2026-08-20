"""SourceTracker — 源可信度模型（ADR-078 §3.6）。

按数据源追踪历史准确率，作为消解策略（可信度加权）的权重输入。
默认采用 Wilson 平滑（避免小样本高置信度）：credibility = (hits + 1) / (total + 2)。

提供：
- record_result(source_id, correct: bool): 记录单次判定结果
- credibility(source_id) -> float: 返回 0~1 可信度（无记录默认 0.5 中性）
- get_weights(sources) -> dict: 归一化权重（供可信度加权策略）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CREDIBILITY = 0.5   # 无历史记录时的中性可信度（Wilson 平滑先验）


@dataclass
class SourceCredibility:
    """单源可信度统计"""
    source_id: str
    hits: int = 0        # 正确次数
    total: int = 0       # 总判定次数

    def credibility(self) -> float:
        """Wilson 平滑可信度（避免小样本过拟合）"""
        return (self.hits + 1.0) / (self.total + 2.0)


class SourceTracker:
    """源可信度追踪器（内存实现，可按需持久化）"""

    def __init__(self):
        self._stats: Dict[str, SourceCredibility] = {}

    def record_result(self, source_id: str, correct: bool) -> None:
        """记录一次判定结果"""
        stat = self._stats.setdefault(source_id, SourceCredibility(source_id=source_id))
        stat.total += 1
        if correct:
            stat.hits += 1

    def credibility(self, source_id: str) -> float:
        """返回源可信度（无记录返回默认 0.5）"""
        stat = self._stats.get(source_id)
        if stat is None:
            return DEFAULT_CREDIBILITY
        return stat.credibility()

    def get_weights(self, sources: List[str]) -> Dict[str, float]:
        """归一化权重（和为 1），供可信度加权策略使用。

        无记录源赋予默认可信度；全默认时均匀分布。
        """
        if not sources:
            return {}
        raw = {s: self.credibility(s) for s in sources}
        total = sum(raw.values())
        if total <= 0:
            n = len(sources)
            return {s: 1.0 / n for s in sources}
        return {s: raw[s] / total for s in sources}

    def stats(self) -> Dict[str, Dict[str, Any]]:
        """导出全部统计（供审计/可视化）"""
        return {
            sid: {"hits": s.hits, "total": s.total, "credibility": s.credibility()}
            for sid, s in self._stats.items()
        }


_instance: Optional[SourceTracker] = None


def get_source_tracker() -> SourceTracker:
    """获取源可信度追踪器单例"""
    global _instance
    if _instance is None:
        _instance = SourceTracker()
    return _instance


__all__ = ["SourceTracker", "SourceCredibility", "get_source_tracker", "DEFAULT_CREDIBILITY"]
