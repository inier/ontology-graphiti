"""
+AI Reasoning Inference — 类型推断与约束建议 (Phase 1 桥接).

当前从 assistant/rules/ 重新导出。
Phase 2 会将实现迁移到此位置。
"""

from odap.biz.core.ontology.assistant.rules.type_inference import (
    TypeInferenceRule,
    infer_entity_type,
)
from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
    ConstraintSuggester,
    suggest_constraints,
)

__all__ = [
    "TypeInferenceRule", "infer_entity_type",
    "ConstraintSuggester", "suggest_constraints",
]
