"""F9 Action 层（AC-40~AC-42）。

「先取证 → 再决策 → 后行动」闭环：
    QaPipeline 产出 `suggested_actions[]`（本包 `derive`）
    → 落 `qa_actions`（`status=proposed`，`repository`）
    → 低风险：一键执行（`service.execute`）
    → 高风险：**必须** HITL 确认后才可执行（`service.decide`，禁自动执行）

对外只暴露 `service.ActionService` 与 `catalog.ACTION_CATALOG`。
"""

from odap.biz.core.ontology.orchestration.actions.catalog import ACTION_CATALOG, ActionSpec
from odap.biz.core.ontology.orchestration.actions.derive import derive_actions
from odap.biz.core.ontology.orchestration.actions.repository import QaActionRepository
from odap.biz.core.ontology.orchestration.actions.service import ActionService

__all__ = [
    "ACTION_CATALOG",
    "ActionSpec",
    "derive_actions",
    "QaActionRepository",
    "ActionService",
]
