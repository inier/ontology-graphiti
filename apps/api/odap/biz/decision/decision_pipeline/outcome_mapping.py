"""`ActionRecord` 状态 -> 决策 `outcome` 的单一映射出口（ADR-091 §5.3）

`_backfill_decision_outcome` 是 outcome 的**唯一回填出口**，映射表单独成模块，
使 8 个 `ActionRequestStatus` 各自落到哪儿能被单测逐行对照，而不是散在
if/elif 里靠读代码推断。

`rolled_back` 曾掉进 `else` 被写成 `outcome=pending`，于是同一个 `pending`
同时表示"还没人裁决""正在执行""跑到一半回滚了"三件事。现落 `failure`：
回滚就是失败，部分达成的事实进 `outcome_details`，不占用 `outcome` 枚举
（一个枚举值只能对应一个界面标签）。
"""

from typing import Any, Dict, List, Optional

from odap.biz.decision.decision_record.models.enums import DecisionOutcome, DecisionStatus
from odap.biz.decision.decision_record.models.status_matrix import StatusOutcomePatch

IN_FLIGHT_OUTCOME = "pending"

# 终结态映射；未列出的状态（pending/validating/approved/executing）留在 pending
TERMINAL_OUTCOMES: Dict[str, str] = {
    "completed": "success",
    "rejected": "rejected",
    "failed": "failure",
    "rolled_back": "failure",
}


def outcome_for(action_status: str, opa_approved: bool = True, has_record: bool = True) -> str:
    """`(opa_approved, action_status)` -> outcome 字符串。

    两条前置路径：
    1. OPA 未通过且根本没产生 ActionRecord -> `rejected`（拒绝留痕）
    2. 其余按执行状态映射；未知状态保守留在 `pending`（不凭空宣布成功或失败）
    """
    if not opa_approved and not has_record:
        return "rejected"
    return TERMINAL_OUTCOMES.get(str(action_status or ""), IN_FLIGHT_OUTCOME)


# outcome -> 流程位置（终态部分；`pending` 要按是否已派发再分，见 status_for）
_STATUS_BY_OUTCOME = {
    "success": "executed",
    "partial_success": "executed",
    "failure": "failed",
    "rejected": "rejected",
}
# 未终结状态下，已派发与未派发的流程位置不同（两者都配 outcome=pending 才合法）
_IN_FLIGHT_STATUS = "executing"
_NOT_YET_DISPATCHED_STATUS = "decided"


def status_for(action_status: str, outcome: str, has_record: bool = True) -> str:
    """`(action_status, outcome)` -> 流程状态。

    必须与 `outcome_for` 成对使用：产出的组合要落在 7 个合法组合内，
    否则写侧矩阵会拒（那说明两张表已经脱节，属内部 bug 而非客户端错误）。
    """
    terminal = _STATUS_BY_OUTCOME.get(outcome)
    if terminal:
        return terminal
    if not has_record:
        return "pending"
    if str(action_status or "") == _IN_FLIGHT_STATUS:
        return _IN_FLIGHT_STATUS
    return _NOT_YET_DISPATCHED_STATUS


def _sub_items(parameters: Any) -> List[str]:
    """从 `parameters["items"]` 取批量子项清单（非字符串列表一律忽略）。"""
    if not isinstance(parameters, dict):
        return []
    items = parameters.get("items")
    if not isinstance(items, list):
        return []
    return [str(item) for item in items]


def rollback_items(action_record: Dict[str, Any]) -> Dict[str, List[str]]:
    """回滚明细：`achieved_items` / `rolled_back_items`。

    这两个字段的定位是"给出可用信息"，不是完备审计（完备审计在 Graphiti Episode），
    因此**不为它们改 `ActionRecord` 表结构**：
    - 批量场景：取 `parameters["items"]` 作为撤销子项
    - 单目标场景：`achieved_items=[]`、`rolled_back_items=[target_object_id]`
    """
    items = _sub_items(action_record.get("parameters"))
    if not items:
        target = action_record.get("target_object_id")
        items = [str(target)] if target else []
    return {"achieved_items": [], "rolled_back_items": items}


def patch_for(
    action_record: Optional[Dict[str, Any]],
    opa_approved: bool = True,
    feedback: Optional[Dict[str, Any]] = None,
) -> StatusOutcomePatch:
    """ActionRecord 快照 -> 单份写侧 patch（status + outcome + details 一次给齐）。

    回填是 status 的四个写点之一：这里就构建 `StatusOutcomePatch`，由存储层
    一次 `SET n += $patch` 落库。任何"先写 outcome 再补 status"的写法都会
    绕开 7/23 矩阵，也会让 `updated_at` 出现第二种写法。
    """
    ar = action_record or {}
    action_status = str(ar.get("status", ""))
    has_record = bool(ar)
    outcome_name = outcome_for(action_status, opa_approved, has_record=has_record)
    details: Dict[str, Any] = {
        "action_record_id": ar.get("action_record_id"),
        "action_status": action_status or None,
        "feedback_pipeline": feedback if isinstance(feedback, dict) else {},
    }
    if action_status == "rolled_back":
        details.update(rollback_items(ar))  # 部分达成的事实进明细，不占 outcome 枚举
    return StatusOutcomePatch(
        status=DecisionStatus(status_for(action_status, outcome_name, has_record)),
        outcome=DecisionOutcome(outcome_name),
        details=details,
    )
