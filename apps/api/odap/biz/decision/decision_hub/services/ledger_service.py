"""台账与待决策队列编排（ADR-091 §3.1 / §3.2 / §5.1.1）

两条硬不变量：
1. **队列不是按单一 status 过滤**，而是按"是否进入待办域"过滤
   （`pending | decided | executing`），再由 `group` 二分。按单一 `pending`
   实现会让 `to_execute` 恒空、计数恒 0——次队列整段消失。
2. **`group` 与 `counts` 同源派生**：两者都出自 `GROUP_STATUSES`，
   否则会出现"分组为空但计数非零"的自相矛盾。
"""

import logging
from dataclasses import replace
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from odap.biz.decision.decision_hub.models import (
    DecisionLedgerPage,
    PendingDecisionItem,
    PendingQueuePage,
    QueueCounts,
)
from odap.biz.decision.decision_hub.services.sla import (
    decided_wait,
    sla_bounds,
    sla_state,
    waited_minutes,
)
from odap.biz.decision.decision_hub.services.state_machine import (
    GROUP_STATUSES,
    available_operations,
    assert_transition,
    derive_group,
    queue_domain_statuses,
)
from odap.biz.decision.decision_record.impl import Neo4jDecisionStore
from odap.biz.decision.decision_record.interfaces import DecisionQuery, IDecisionStore
from odap.biz.decision.decision_record.models import DecisionRecord
from odap.biz.decision.decision_record.models.timestamps import utcnow

logger = logging.getLogger(__name__)

# 队列排序：waited_desc 即 created_at 升序（等待最久的在最上）
_QUEUE_SORT = {
    "waited_desc": ("created_at", "asc"),
    "created_asc": ("created_at", "asc"),
    "confidence_asc": ("confidence", "asc"),
}

# SLA 计数的计时基准：与 `_to_item` 的派生口径一一对应，不可统一成 created_at
_SLA_FIELDS = {"to_resolve": "created_at", "to_execute": "decided_at"}


class LedgerService:
    """决策台账 / 待决策队列读侧（写侧与状态迁移不在本服务）。"""

    def __init__(
        self,
        store: Optional[IDecisionStore] = None,
        now_provider: Callable[[], datetime] = utcnow,
    ) -> None:
        self.store: IDecisionStore = store or Neo4jDecisionStore()
        self._now = now_provider

    # ---------------- 台账 ----------------

    async def list_ledger(self, query: DecisionQuery, page: int, page_size: int) -> DecisionLedgerPage:
        """台账分页：`has_more` 在估算态以"是否取满一页"判定，不依赖 total。"""
        await self.store.ensure_indices()  # 读路径自愈：顺带跑一次幂等迁移
        skip = (page - 1) * page_size
        items = await self.store.list_decisions(query, skip=skip, limit=page_size)
        total, is_estimate = await self.store.count_decisions(query)
        has_more = len(items) == page_size if is_estimate else (skip + len(items)) < total
        return DecisionLedgerPage(
            items=items,
            total=total,
            total_is_estimate=is_estimate,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    # ---------------- 待决策队列 ----------------

    async def list_pending(
        self,
        query: DecisionQuery,
        group: str = "all",
        sort_by: str = "waited_desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PendingQueuePage:
        """待决策队列：待办域三态 + 双分组 + 四计数 + SLA 派生。"""
        base = self._queue_base(query, sort_by)
        skip = (page - 1) * page_size
        records = await self._fetch_groups(base, group, skip, page_size)
        now = self._now()
        counts = await self._counts(base, now)
        total = counts.to_resolve + counts.to_execute
        # has_more 必须按**当前 group 的条数**判定：用整域 total 比会让
        # "to_resolve 最后一页"也显示还有下一页（另一种"各说一套"）
        scope_total = total
        if group == "to_resolve":
            scope_total = counts.to_resolve
        elif group == "to_execute":
            scope_total = counts.to_execute
        return PendingQueuePage(
            items=[self._to_item(record, now) for record in records],
            total=total,
            counts=counts,
            page=page,
            page_size=page_size,
            has_more=skip + len(records) < scope_total,
        )

    def _queue_base(self, query: DecisionQuery, sort_by: str) -> DecisionQuery:
        """构造队列基础条件：状态域与排序由服务端硬注入，客户端只能收窄。"""
        sort_field, order = _QUEUE_SORT.get(sort_by, _QUEUE_SORT["waited_desc"])
        return replace(
            query,
            statuses=queue_domain_statuses(),  # 硬编码待办域，无视客户端 statuses
            outcomes=(),
            exclude_assumed=True,              # 历史推定记录不进队列（PM E29）
            sort_by=sort_field,
            order=order,
        )

    async def _fetch_groups(
        self, base: DecisionQuery, group: str, skip: int, page_size: int
    ) -> List[DecisionRecord]:
        """取当页记录：`group=all` 时先 to_resolve 后 to_execute（组内按 sort 规则）。"""
        if group in GROUP_STATUSES:
            return await self.store.list_decisions(
                replace(base, statuses=GROUP_STATUSES[group]), skip=skip, limit=page_size
            )
        records: List[DecisionRecord] = []
        for name in ("to_resolve", "to_execute"):
            records.extend(
                await self.store.list_decisions(
                    replace(base, statuses=GROUP_STATUSES[name]), skip=0, limit=skip + page_size
                )
            )
        return records[skip : skip + page_size]

    async def _counts(self, base: DecisionQuery, now: datetime) -> QueueCounts:
        """四个计数与 items 同源：分组取自 GROUP_STATUSES，SLA 取自分档时间区间。"""
        total, _ = await self.store.count_decisions(base, probe=0)
        to_resolve, _ = await self.store.count_decisions(
            replace(base, statuses=GROUP_STATUSES["to_resolve"]), probe=0
        )
        warning, breached = await self._sla_counts(base, now)
        # 待办域 = to_resolve ∪ to_execute，故 to_execute 由总数减去 to_resolve 得出，
        # 不另写一遍 status 条件（否则两处条件漂移会出现"分组为空但计数非零"）
        return QueueCounts(
            to_resolve=to_resolve,
            to_execute=total - to_resolve,
            sla_warning=warning,
            sla_breached=breached,
        )

    async def _sla_counts(self, base: DecisionQuery, now: datetime) -> Tuple[int, int]:
        """SLA 计数：两个分组各按自己的计时基准取区间（全库口径，与分页无关）。"""
        warning_from, warning_to, breached_to = sla_bounds(now)
        warning = breached = 0
        for group, field in _SLA_FIELDS.items():
            scope = replace(base, statuses=GROUP_STATUSES[group], time_field=field)
            warning += await self._count(scope, created_from=warning_from, created_to=warning_to)
            breached += await self._count(scope, created_to=breached_to)
        return warning, breached

    async def _count(self, query: DecisionQuery, **bounds) -> int:
        """精确计数（`probe=0`）：队列四计数必须是全库值，不能是估算或页内值。"""
        total, _ = await self.store.count_decisions(replace(query, **bounds), probe=0)
        return total

    def _to_item(self, record: DecisionRecord, now: datetime) -> PendingDecisionItem:
        """条目派生：分组、两个等待时长、SLA 状态、可做动作。"""
        group = derive_group(record.status.value)
        if group is None:  # 理论上不可达（域已过滤），兜底不静默降级
            logger.warning("决策 %s 状态 %s 不属于待办域", record.decision_id, record.status.value)
            group = "to_resolve"
        waited = waited_minutes(record.created_at, now)
        decided_minutes, sla_minutes = self._basis(record, group, now, waited)
        return PendingDecisionItem(
            decision=record,
            group=group,
            waited_minutes=waited,
            decided_waited_minutes=decided_minutes,
            sla_state=sla_state(sla_minutes),
            available_operations=available_operations(record.status.value),
            executable=record.recommended_action is not None,
        )

    def _basis(
        self, record: DecisionRecord, group: str, now: datetime, waited: int
    ) -> Tuple[Optional[int], int]:
        """返回 `(decided_waited_minutes, 用于 SLA 判定的分钟数)`。

        `to_resolve` 档没有裁决时刻，两个值分别是 `None` 与自创建起算的分钟数。
        """
        if group != "to_execute":
            return None, waited
        return decided_wait(record.resolution, record.updated_at, now, record.decision_id)


__all__ = ["LedgerService", "assert_transition"]


_service: Optional[LedgerService] = None


def get_ledger_service() -> LedgerService:
    """台账服务单例（FastAPI 依赖，测试可整体替换 store）。"""
    global _service
    if _service is None:
        _service = LedgerService()
    return _service
