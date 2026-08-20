"""+AI Reasoning — 推理技术能力层（非领域层）。

提供横向AI增强能力: 类型推断、约束建议、一致性校验、统一检索、
确定性推理（ADR-075）与混合策略。
"""

from .contract.interface import (
    ReasoningServiceContract,
    TypeInferenceResult, ConstraintSuggestion, ConsistencyReport,
)
from .services.unified_retrieve import (
    RetrieveRequest, RetrieveResult,
    UnifiedRetrieveEngine, get_retrieve_engine,
)
from .engines.deterministic.datalog_engine import (
    DatalogEngine, ReasoningResult,
)
from .engines.deterministic.rule_loader import RuleLoader, RuleValidationError
from .engines.deterministic.fact_loader import FactLoader, Fact, facts_to_clauses
from .engines.deterministic.trace_builder import TraceBuilder, RuleTrace
from .engines.hybrid.hybrid_strategy import HybridStrategy, HybridOutcome
from .impl.unified_reasoning_service import (
    UnifiedReasoningServiceV2, get_reasoning_service_v2,
)
from .rules.models import BusinessRule, RulePriority

__all__ = [
    "ReasoningServiceContract",
    "TypeInferenceResult", "ConstraintSuggestion", "ConsistencyReport",
    "RetrieveRequest", "RetrieveResult",
    "UnifiedRetrieveEngine", "get_retrieve_engine",
    "DatalogEngine", "ReasoningResult",
    "RuleLoader", "RuleValidationError",
    "FactLoader", "Fact", "facts_to_clauses",
    "TraceBuilder", "RuleTrace",
    "HybridStrategy", "HybridOutcome",
    "UnifiedReasoningServiceV2", "get_reasoning_service_v2",
    "BusinessRule", "RulePriority",
]
