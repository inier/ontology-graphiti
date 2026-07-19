"""
+AI Reasoning Consistency — 跨层一致性校验 (Phase 1 桥接).

当前从 design/services/validation_service 和 health/ 重新导出。
Phase 2 会将实现迁移到此位置。
"""

# Schema-level validation
from odap.biz.core.ontology.design.services.validation_service import (
    ValidationService,
)

__all__ = [
    "ValidationService",
]
