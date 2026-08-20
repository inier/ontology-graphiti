"""冲突检测与消解（ADR-078 §3.6）。

核心原则：冲突**标记而非覆盖**——多源汇聚时静默覆盖是数据质量灾难。
消解策略库：可信度加权 / 最近优先 / 投票；配套 SourceTracker 源可信度模型。

子模块：
- models:          Conflict / ConflictType / ConflictReport
- detector:        ConflictDetector 属性/类型/关系/时态冲突检测
- resolution:      ResolutionStrategy 消解策略库
- source_tracker:  SourceTracker 源可信度（按数据源追踪历史准确率）
"""

from .models import (
    Conflict, ConflictType, ConflictReport, ConflictSeverity,
)
from .detector import ConflictDetector
from .resolution import (
    ResolutionStrategy, ConfidenceWeightedStrategy,
    LatestWinsStrategy, MajorityVoteStrategy, resolve_conflict,
)
from .source_tracker import SourceTracker, SourceCredibility

__all__ = [
    "Conflict", "ConflictType", "ConflictReport", "ConflictSeverity",
    "ConflictDetector",
    "ResolutionStrategy", "ConfidenceWeightedStrategy",
    "LatestWinsStrategy", "MajorityVoteStrategy", "resolve_conflict",
    "SourceTracker", "SourceCredibility",
]
