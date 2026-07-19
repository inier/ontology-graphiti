"""+AI Reasoning — 推理技术能力层（非领域层）。

提供横向AI增强能力: 类型推断、约束建议、一致性校验、统一检索。
"""

from .contract.interface import (
    ReasoningServiceContract,
    TypeInferenceResult, ConstraintSuggestion, ConsistencyReport,
)
from .services.unified_retrieve import (
    RetrieveRequest, RetrieveResult,
    UnifiedRetrieveEngine, get_retrieve_engine,
)

__all__ = [
    "ReasoningServiceContract",
    "TypeInferenceResult", "ConstraintSuggestion", "ConsistencyReport",
    "RetrieveRequest", "RetrieveResult",
    "UnifiedRetrieveEngine", "get_retrieve_engine",
]
