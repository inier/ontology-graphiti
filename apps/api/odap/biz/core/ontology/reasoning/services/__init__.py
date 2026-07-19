"""+AI Reasoning Services.

组合 inference/ 和 consistency/ 的能力，对外暴露:
- UnifiedReasoningService: 统一推理服务入口 (ReasoningServiceContract 完整实现)
- UnifiedRetrieveEngine: 全平台统一检索引擎
- 相关 DTO (RetrieveRequest, RetrieveResult)
"""

from .unified_reasoning import UnifiedReasoningService, get_reasoning_service
from .unified_retrieve import (
    RetrieveRequest, RetrieveResult,
    UnifiedRetrieveEngine, get_retrieve_engine,
)


__all__ = [
    "UnifiedReasoningService", "get_reasoning_service",
    "RetrieveRequest", "RetrieveResult",
    "UnifiedRetrieveEngine", "get_retrieve_engine",
]
