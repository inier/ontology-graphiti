"""决策查询对象（ADR-091 §5.2）

台账与队列共用同一个查询对象，避免 12 个过滤参数在两处各写一遍，
也把"哪些条件参与过滤"收敛成一处，便于审计与单测。
"""

from dataclasses import dataclass
from typing import Optional, Tuple

LEDGER_SORT_FIELDS = ("created_at", "updated_at", "confidence", "evidence_count")
SORT_ORDERS = ("asc", "desc")
# 时间区间过滤的计时基准白名单（SLA 计数按分组取不同基准）
TIME_FIELDS = ("created_at", "updated_at", "decided_at")


@dataclass(frozen=True)
class DecisionQuery:
    """决策查询条件（不可变，收窄时用 `dataclasses.replace`）。

    `exclude_assumed` 默认 `True` 是故意的：唯一传 `False` 的调用方是台账
    （要看全量），漏传的后果只是"队列少几条历史假数据"，而不是
    "队列被历史数据淹掉"。默认值应把系统往安全侧推。

    `time_field` 决定 `created_from` / `created_to` 作用在哪个时间列上：
    待裁定档用 `created_at`，待执行确认档用 `decided_at`（裁决时刻）。
    """

    workspace_id: str
    statuses: Tuple[str, ...] = ()
    outcomes: Tuple[str, ...] = ()            # 多值：success + partial_success 需同时命中
    entry_source: Optional[str] = None
    decision_type: Optional[str] = None
    agent_id: Optional[str] = None            # 空间内收窄维度，不是租户边界
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    text_query: Optional[str] = None          # 只搜 context_summary / recommended_option
    created_from: Optional[str] = None        # 归一化 UTC 定宽 ISO8601，作用见 time_field
    created_to: Optional[str] = None
    time_field: str = "created_at"            # created_at / updated_at / decided_at
    exclude_assumed: bool = True
    sort_by: str = "created_at"
    order: str = "desc"

    def validate(self) -> None:
        """参数自洽校验（路由层已做，这里兜底防内部调用传错）。"""
        if not self.workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
        if self.sort_by not in LEDGER_SORT_FIELDS:
            raise ValueError(f"不支持的排序字段: {self.sort_by}")
        if self.order not in SORT_ORDERS:
            raise ValueError(f"不支持的排序方向: {self.order}")
        if self.time_field not in TIME_FIELDS:
            raise ValueError(f"不支持的计时基准: {self.time_field}")
        if (
            self.min_confidence is not None
            and self.max_confidence is not None
            and self.min_confidence > self.max_confidence
        ):
            raise ValueError("min_confidence 不得大于 max_confidence")
