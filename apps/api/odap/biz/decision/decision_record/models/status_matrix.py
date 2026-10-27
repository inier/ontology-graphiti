"""`status` × `outcome` 合法组合矩阵（ADR-091 §5.1.2 / E33 / E34）

两个状态字段并存的最大风险是出现 `status=executed` 但 `outcome=pending`
这类矛盾态——谁都不知道该信哪个。故把 6 × 5 = 30 个组合穷举成常量表：
**合法 7 个，非法 23 个**。

校验落点分两侧，这一点不能做错：
- **写侧拒绝**：`StatusOutcomePatch` 用 `model_validator` 在构造时就拒绝非法组合，
  使漂移从"事后对账"变成"写不进去"。status 与 outcome 由 `to_node_patch()`
  合成同一份 patch，天然同一次原子写（E34）。
- **读侧只告警**：`DecisionRecord` 是从图节点反序列化的，硬校验会让任何一条
  历史脏数据在**读取**时抛异常，列表页直接 500。故 `reconcile_on_read` 只告警，
  并让调用方以 `status` 为准（流程位置比执行结果更可信）。
"""

import json
import logging
from typing import Any, Dict, FrozenSet, Optional

from pydantic import BaseModel, Field, model_validator

from odap.biz.decision.decision_record.models.enums import DecisionOutcome, DecisionStatus
from odap.biz.decision.decision_record.models.timestamps import iso_utc, utcnow

logger = logging.getLogger(__name__)


class DecisionInvariantError(Exception):
    """非法 `status × outcome` 组合：内部不变量被破坏 → **500**（不是 400，也不是 409）。

    刻意**不继承 `ValueError`**：`ExceptionHandlerMiddleware` 把任何 `ValueError`
    映射成 400 + `{"error": {...}}` 信封，而 `pydantic.ValidationError` 本身就是
    `ValueError` 子类。沿用 `ValueError` 会让非法组合以 400 返回，把"内部 bug"伪装成
    "客户端参数错"。

    **为什么是 500 而不是 409**：四个写入方全是服务端代码（建/裁决/派发/回填），
    正常请求根本不可达；一旦触发，说明矩阵与调用方已经脱节，是 bug。而 409 的语义是
    「你和别人撞了，换条路再试」——把它挂在这里会让排查方向指向并发，而现场没有并发。
    **可预期的客户端错误（非法迁移/被抢先）用 `ConflictError(code="illegal_transition")`。**
    """


# status -> 允许的 outcome 集合
LEGAL_OUTCOMES: Dict[str, FrozenSet[str]] = {
    "pending": frozenset({"pending"}),
    "decided": frozenset({"pending"}),
    "executing": frozenset({"pending"}),
    # 不变量：每个 outcome 只能对应一个界面标签。partial_success 仅在 executed 下合法，
    # 它是「部分成功」标签的唯一来源；failed 只收 failure，回滚也归 failure——
    # 否则同一个 partial_success 会同时意味着「做了一半」和「做完又撤了」，标签无法自洽。
    "executed": frozenset({"success", "partial_success"}),
    "failed": frozenset({"failure"}),
    "rejected": frozenset({"rejected"}),
}


def is_legal(status: str, outcome: str) -> bool:
    """组合是否合法（未知 status 视为非法，fail-closed）。"""
    allowed = LEGAL_OUTCOMES.get(status)
    return bool(allowed) and outcome in allowed


def assert_legal(status: str, outcome: str) -> None:
    """写侧断言：非法组合抛 `DecisionInvariantError` → 500（内部 bug，非客户端错误）。"""
    if not is_legal(status, outcome):
        raise DecisionInvariantError(
            f"非法的 status/outcome 组合: status={status}, outcome={outcome}；"
            f"允许的 outcome 为 {sorted(LEGAL_OUTCOMES.get(status, frozenset()))}"
        )


def reconcile_on_read(status: str, outcome: str, decision_id: str = "") -> Optional[str]:
    """读侧校准：合法返回 None，非法返回告警文案并记录 warning（绝不抛错）。"""
    if is_legal(status, outcome):
        return None
    message = (
        f"决策 {decision_id or '<unknown>'} 的 status/outcome 组合非法"
        f"（status={status}, outcome={outcome}），读取侧以 status 为准"
    )
    logger.warning(message)
    return message


class StatusOutcomePatch(BaseModel):
    """状态写侧载荷：`status` 与 `outcome` 必须同时给、同时写。

    `details` 是 `outcome_details` 的内容（`action_status` / `achieved_items` 等），
    由 `to_node_patch()` 序列化进**同一个** `outcome_details` 属性，与 status/outcome
    合成单份 `SET n += $patch`。

    为什么不把 `details` 摊平成节点顶层属性：它会覆盖节点既有属性（客户端可通过
    `outcome_details` 传入 `decision_id` 覆盖主键）；而读侧 `from_node_properties`
    只从 `outcome_details` 取这些键，摊平后详情页会读到空对象。
    """

    status: DecisionStatus
    outcome: DecisionOutcome
    details: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_illegal_combination(self) -> "StatusOutcomePatch":
        assert_legal(self.status.value, self.outcome.value)
        return self

    def to_node_patch(self) -> Dict[str, Any]:
        """合成单份节点 patch（status 与 outcome 同事务原子写，E34）。"""
        return {
            "status": self.status.value,
            "outcome": self.outcome.value,
            "outcome_details": json.dumps(self.details, ensure_ascii=False, default=str),
            "updated_at": iso_utc(utcnow()),
        }
