"""动作目录 —— 风险分类的唯一真源（AC-40 / AC-41）。

为什么是「目录」而不是「运行时猜测」：
- `risk_level` 决定是否必须走 HITL，属安全属性，**不能**由 LLM 或启发式决定；
- 未登记的动作类型一律拒绝（fail-closed），避免新动作绕过 HITL。

分类原则：
- `low`  = 只读 / 预览，无副作用，可一键执行；
- `high` = 写入 / 对外发布 / 不可逆，**必须** HITL 确认（`requires_hitl=True`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

RISK_LOW = "low"
RISK_HIGH = "high"


@dataclass(frozen=True)
class ActionSpec:
    """一个可建议动作的静态定义（不可变，进程内全局共享）。"""

    action_type: str
    risk_level: str
    executable: bool
    summary: str

    @property
    def requires_hitl(self) -> bool:
        """高风险动作必须人工确认（AC-41）。"""
        return self.risk_level == RISK_HIGH


#: 动作目录（新增动作必须在此登记，否则 `spec_for` 返回 None → 拒绝）
ACTION_CATALOG: Dict[str, ActionSpec] = {
    spec.action_type: spec
    for spec in (
        ActionSpec(
            action_type="open_provenance",
            risk_level=RISK_LOW,
            executable=True,
            summary="查看本次回答的六步溯源证据链",
        ),
        ActionSpec(
            action_type="view_citations",
            risk_level=RISK_LOW,
            executable=True,
            summary="查看本次回答引用的证据清单",
        ),
        ActionSpec(
            action_type="submit_gap_fill",
            risk_level=RISK_HIGH,
            executable=True,
            summary="把未映射的概念槽位提交为本体缺口（写 gap_pool）",
        ),
        ActionSpec(
            action_type="export_answer_wiki",
            risk_level=RISK_HIGH,
            executable=False,
            summary="把本次答案导出为 Wiki 条目（对外发布，需审批）",
        ),
    )
}


def spec_for(action_type: str) -> Optional[ActionSpec]:
    """取动作定义；未登记返回 None（调用方据此拒绝，不猜风险等级）。"""
    return ACTION_CATALOG.get(action_type or "")


__all__ = ["ActionSpec", "ACTION_CATALOG", "spec_for", "RISK_LOW", "RISK_HIGH"]
