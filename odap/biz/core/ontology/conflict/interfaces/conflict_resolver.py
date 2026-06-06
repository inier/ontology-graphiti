"""
冲突解决器 - 抽象接口 (T314)

定义 ConflictResolver ABC，规范冲突检测与解决行为。
实现方必须提供 detect_conflicts 与 resolve 两个方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models import (
    ConflictRecord,
    ConflictResolution,
    ResolutionResult,
)


class ConflictResolver(ABC):
    """冲突解决器抽象基类"""

    @abstractmethod
    def detect_conflicts(self, sources: List[Dict[str, Any]]) -> List[ConflictRecord]:
        """
        从多源数据中检测冲突。

        Args:
            sources: 多个数据源的快照列表，每项含 source_id + 实体快照。

        Returns:
            冲突记录列表（每条 ConflictRecord 含 entity_id/field/candidates）。
        """
        raise NotImplementedError

    @abstractmethod
    def resolve(
        self,
        conflict: ConflictRecord,
        strategy: ConflictResolution,
        context: Dict[str, Any] | None = None,
    ) -> ResolutionResult:
        """
        依据给定策略解决单条冲突。

        Args:
            conflict: 待解决的冲突记录。
            strategy: 解决策略（FIRST_WINS/LAST_WINS/LLM_JUDGE/MANUAL）。
            context: 附加上下文（如 LLM 调用所需的 ontology/workspace 元数据）。

        Returns:
            ResolutionResult：包含选定候选 + 解决状态 + 理由。
        """
        raise NotImplementedError
