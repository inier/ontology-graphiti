"""
+AI Reasoning Inference — 类型推断与约束建议 (Phase 1 桥接).

当前从 assistant/rules/ 重新导出。
Phase 2 会将实现迁移到此位置。

注：`TypeInferenceRule` / `infer_entity_type` / `suggest_constraints` 已被重构为
`TypeInferenceEngine` / `ConstraintSuggester` 的方法，模块级符号不再存在；
此前仍按旧符号 re-export，导致本包在 import 期就抛 ImportError。
"""

from odap.biz.core.ontology.assistant.rules.type_inference import TypeInferenceEngine
from odap.biz.core.ontology.assistant.rules.constraint_suggester import ConstraintSuggester

__all__ = [
    "TypeInferenceEngine",
    "ConstraintSuggester",
]
