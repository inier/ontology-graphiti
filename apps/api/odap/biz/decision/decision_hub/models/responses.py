"""台账与队列的响应模型（对齐 api-spec `DecisionLedgerPage` / `PendingQueuePage`）"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from odap.biz.decision.decision_record.models import DecisionRecord

QueueGroup = Literal["to_resolve", "to_execute"]
SlaState = Literal["ok", "warning", "breached"]
OperationName = Literal["approve", "reject", "execute", "retry"]


class DecisionLedgerPage(BaseModel):
    """决策台账分页。`total_is_estimate` 恒返回，前端无需分支判空。"""

    items: List[DecisionRecord] = Field(default_factory=list)
    total: int = Field(description="总数；估算态时为探测上限值")
    total_is_estimate: bool = Field(
        default=False, description="true 表示 total 是探测值（= 探测上限），非精确总数"
    )
    page: int
    page_size: int
    has_more: bool


class QueueCounts(BaseModel):
    """四个计数由与 items 完全相同的过滤条件派生，不受分页影响。"""

    to_resolve: int = Field(description="待裁定条目数")
    to_execute: int = Field(description="待执行确认条目数（decided + executing）")
    sla_warning: int = Field(description="等待 24-72h 的条目数")
    sla_breached: int = Field(description="等待 > 72h 的条目数")


class PendingDecisionItem(BaseModel):
    """队列条目：状态机派生字段由服务端给齐，前端不自行推断。

    两个等待时长服务两个分组，**不可互换**：
    - `waited_minutes` 自 `created_at` 起算，配 `to_resolve`（等了多久没人拍板）
    - `decided_waited_minutes` 自 `resolution.at` 起算，配 `to_execute`
      （拍板后多久没落地）；`to_resolve` 行恒为 `null`
    `sla_state` 的计时基准随 `group` 取（见 `services/sla.decided_wait`）。
    """

    decision: DecisionRecord
    group: QueueGroup = Field(description="to_resolve = 待裁定；to_execute = 待执行确认")
    waited_minutes: int = Field(ge=0, description="自 created_at 起算的等待分钟数")
    decided_waited_minutes: Optional[int] = Field(
        ge=0, description="自 resolution.at 起算的等待分钟数；无裁决时刻为 null"
    )
    sla_state: SlaState = Field(description="后端派生：ok / warning / breached")
    available_operations: List[OperationName] = Field(
        default_factory=list, description="当前可做的动作；为空时前端不渲染按钮组"
    )
    executable: bool = Field(description="recommended_action 非空（仅表示有载荷）")


class PendingQueuePage(BaseModel):
    """待决策队列分页（两段分组 + 四计数，一次请求渲染）。"""

    items: List[PendingDecisionItem] = Field(default_factory=list)
    total: int = Field(description="待办域（pending + decided + executing）精确总条数")
    counts: QueueCounts
    page: int
    page_size: int
    has_more: bool
