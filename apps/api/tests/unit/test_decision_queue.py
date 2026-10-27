"""T4/T5 待决策队列：分组、四计数、分档 SLA 计时基准

本文件只测队列（台账见 `test_decision_hub.py`）。核心不变量：

1. **`sla_state` 的计时基准按 `group` 分档**：`to_resolve` 自 `created_at`、
   `to_execute` 自 `resolution.at`。统一取 `created_at` 会把"昨天刚裁决的"
   显示成"等了 5 天"，而 `to_execute` 档存在的意义正是"拍板后多久还没落地"。
2. **`counts` 是全库口径**，与 `items` 同源、不受分页影响；`to_execute` 由
   "域总数 - to_resolve" 得出，条件只写一遍。
3. **`status_assumed=true` 在数据层排除**（队列条目与四个计数都不许出现），
   不靠前端过滤——否则计数与列表会各说一套。
"""

from datetime import datetime, timedelta, timezone

import pytest

from odap.biz.decision.decision_hub.services.ledger_service import LedgerService
from odap.biz.decision.decision_record.interfaces import DecisionQuery
from odap.biz.decision.decision_record.models import (
    DecisionOutcome,
    DecisionRecord,
    DecisionStatus,
)

from decision_fakes import InMemoryDecisionStore

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _record(
    hours_ago: float = 0.0,
    status: DecisionStatus = DecisionStatus.PENDING,
    outcome: DecisionOutcome = DecisionOutcome.PENDING,
    decided_hours_ago: float = None,
    workspace_id: str = "ws-a",
    **kwargs,
) -> DecisionRecord:
    created = NOW - timedelta(hours=hours_ago)
    resolution = None
    if decided_hours_ago is not None:
        resolution = {"action": "approve", "actor_type": "user", "by": "张三",
                      "at": (NOW - timedelta(hours=decided_hours_ago)).isoformat(),
                      "reason": ""}
    return DecisionRecord(
        workspace_id=workspace_id,
        context_summary=kwargs.pop("context_summary", "供应商主数据漂移"),
        status=status,
        outcome=outcome,
        resolution=kwargs.pop("resolution", resolution),
        recommended_action=kwargs.pop("recommended_action", None),
        created_at=created,
        updated_at=kwargs.pop("updated_at", created),
        valid_at=created,
        **kwargs,
    )


@pytest.fixture
def queue_service():
    store = InMemoryDecisionStore(
        [
            _record(hours_ago=1, status=DecisionStatus.PENDING),
            _record(hours_ago=30, status=DecisionStatus.PENDING),
            _record(hours_ago=100, status=DecisionStatus.PENDING),
            _record(hours_ago=2, status=DecisionStatus.DECIDED, decided_hours_ago=1,
                    recommended_action={"action_type_id": "freeze"}),
            _record(hours_ago=3, status=DecisionStatus.EXECUTING, decided_hours_ago=2),
            _record(hours_ago=4, status=DecisionStatus.EXECUTED, outcome=DecisionOutcome.SUCCESS),
            _record(hours_ago=5, status=DecisionStatus.REJECTED, outcome=DecisionOutcome.REJECTED),
        ]
    )
    return LedgerService(store=store, now_provider=lambda: NOW)


@pytest.mark.asyncio
async def test_queue_only_contains_pending_domain(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"))
    statuses = {item.decision.status.value for item in page.items}
    assert statuses == {"pending", "decided", "executing"}
    assert page.total == 5


@pytest.mark.asyncio
async def test_queue_counts_match_group_items(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)

    to_resolve = [i for i in page.items if i.group == "to_resolve"]
    to_execute = [i for i in page.items if i.group == "to_execute"]

    assert page.counts.to_resolve == len(to_resolve) == 3
    assert page.counts.to_execute == len(to_execute) == 2


@pytest.mark.asyncio
async def test_queue_sla_counts_are_derived_from_same_filter(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    warning = [i for i in page.items if i.sla_state == "warning"]
    breached = [i for i in page.items if i.sla_state == "breached"]
    assert page.counts.sla_warning == len(warning) == 1
    assert page.counts.sla_breached == len(breached) == 1


@pytest.mark.asyncio
async def test_queue_excludes_assumed_legacy_records(queue_service):
    queue_service.store.records.extend(
        [_record(hours_ago=6, status_assumed=True) for _ in range(5)]
    )
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    assert page.total == 5  # 5 条历史推定记录不进队列


@pytest.mark.asyncio
async def test_assumed_records_absent_from_items_and_counts(queue_service):
    """推定态记录在条目、分组计数、SLA 计数三处都不得出现（PM 提示只测 total 会漏）。"""
    queue_service.store.records.extend(
        [_record(hours_ago=100, status_assumed=True) for _ in range(5)]
    )
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    assert page.counts.to_resolve == 3
    assert page.counts.sla_breached == 1
    assert all(not i.decision.status_assumed for i in page.items)


@pytest.mark.asyncio
async def test_queue_group_filter_narrows(queue_service):
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a"), group="to_resolve", page_size=100
    )
    assert {i.group for i in page.items} == {"to_resolve"}
    assert page.counts.to_execute == 2  # 计数不随 group 收窄而变


@pytest.mark.asyncio
async def test_queue_has_more_uses_group_scope(queue_service):
    # 收窄到 to_resolve 时，has_more 必须按该组条数判定，不能拿整域总数比
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a"), group="to_resolve", page_size=20
    )
    assert len(page.items) == 3
    assert page.has_more is False


@pytest.mark.asyncio
async def test_queue_has_more_true_when_group_page_is_partial(queue_service):
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a"), group="to_resolve", page_size=2
    )
    assert len(page.items) == 2
    assert page.has_more is True


@pytest.mark.asyncio
async def test_queue_has_more_false_on_last_page_of_all(queue_service):
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a"), group="all", page_size=3, page=2
    )
    assert len(page.items) == 2
    assert page.has_more is False


@pytest.mark.asyncio
async def test_queue_orders_to_resolve_before_to_execute(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    groups = [i.group for i in page.items]
    assert groups == sorted(groups, key=lambda g: 0 if g == "to_resolve" else 1)


@pytest.mark.asyncio
async def test_queue_items_carry_operations_and_executable_flag(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    by_status = {item.decision.status.value: item for item in page.items}
    assert by_status["pending"].available_operations == ["approve", "reject"]
    assert by_status["pending"].executable is False
    assert by_status["decided"].available_operations == ["execute"]
    assert by_status["decided"].executable is True
    assert by_status["executing"].available_operations == []


@pytest.mark.asyncio
async def test_queue_waited_minutes_from_created_at(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    waits = sorted(i.waited_minutes for i in page.items)
    assert waits == [60, 120, 180, 1800, 6000]


# ---------------- 分档 SLA：to_execute 自 resolution.at 起算 ----------------


@pytest.mark.asyncio
async def test_to_execute_sla_uses_resolution_at(queue_service):
    """创建 5 天前但 1 小时前才裁决：SLA 必须是 ok（两个等待时长相差一整个周期）。"""
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    decided = [i for i in page.items if i.decision.status.value == "decided"][0]

    assert decided.waited_minutes == 2 * 60        # 自 created_at
    assert decided.decided_waited_minutes == 60    # 自 resolution.at
    assert decided.sla_state == "ok"               # 基准是 resolution.at


@pytest.mark.asyncio
async def test_to_execute_long_wait_is_breached_by_decided_at():
    store = InMemoryDecisionStore(
        [_record(hours_ago=200, status=DecisionStatus.DECIDED, decided_hours_ago=100)]
    )
    page = await LedgerService(store=store, now_provider=lambda: NOW).list_pending(
        DecisionQuery(workspace_id="ws-a"), page_size=100
    )
    item = page.items[0]
    assert item.decided_waited_minutes == 6000
    assert item.sla_state == "breached"
    assert page.counts.sla_breached == 1


@pytest.mark.asyncio
async def test_to_resolve_decided_waited_minutes_is_null(queue_service):
    page = await queue_service.list_pending(DecisionQuery(workspace_id="ws-a"), page_size=100)
    for item in page.items:
        if item.group == "to_resolve":
            assert item.decided_waited_minutes is None


@pytest.mark.asyncio
async def test_to_execute_without_resolution_falls_back_to_updated_at(caplog):
    """缺 resolution.at 的异常记录：字段留 null，SLA 判定回落 updated_at 且告警。"""
    store = InMemoryDecisionStore(
        [_record(hours_ago=200, status=DecisionStatus.DECIDED,
                 updated_at=NOW - timedelta(hours=100))]
    )
    with caplog.at_level("WARNING"):
        page = await LedgerService(store=store, now_provider=lambda: NOW).list_pending(
            DecisionQuery(workspace_id="ws-a"), page_size=100
        )
    item = page.items[0]
    assert item.decided_waited_minutes is None
    assert item.sla_state == "breached"
    assert any("resolution" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_sla_counts_use_group_basis_not_created_at():
    """计数与条目必须取同一计时基准，否则"徽标与数字互相打脸"。"""
    store = InMemoryDecisionStore(
        [
            # 创建 5 天前、1 小时前裁决：按 created_at 会计成 breached（错）
            _record(hours_ago=120, status=DecisionStatus.DECIDED, decided_hours_ago=1),
            # 待裁定 100 小时：breached（对）
            _record(hours_ago=100, status=DecisionStatus.PENDING),
            # 待裁定 30 小时：warning（对）
            _record(hours_ago=30, status=DecisionStatus.PENDING),
        ]
    )
    page = await LedgerService(store=store, now_provider=lambda: NOW).list_pending(
        DecisionQuery(workspace_id="ws-a"), page_size=100
    )
    assert page.counts.sla_warning == 1
    assert page.counts.sla_breached == 1
    assert {i.sla_state for i in page.items if i.group == "to_execute"} == {"ok"}


@pytest.mark.asyncio
async def test_to_execute_count_matches_group_presence():
    """造 3 条 decided -> 计数 3 且次队列非空；造 0 条 -> 计数 0 且次队列为空。"""
    full = InMemoryDecisionStore(
        [_record(hours_ago=1, status=DecisionStatus.DECIDED, decided_hours_ago=1) for _ in range(3)]
    )
    page = await LedgerService(store=full, now_provider=lambda: NOW).list_pending(
        DecisionQuery(workspace_id="ws-a"), page_size=100
    )
    assert page.counts.to_execute == 3
    assert [i.group for i in page.items if i.group == "to_execute"] != []

    empty = InMemoryDecisionStore([_record(hours_ago=1, status=DecisionStatus.PENDING)])
    page = await LedgerService(store=empty, now_provider=lambda: NOW).list_pending(
        DecisionQuery(workspace_id="ws-a"), page_size=100
    )
    assert page.counts.to_execute == 0
    assert [i for i in page.items if i.group == "to_execute"] == []


@pytest.mark.asyncio
async def test_queue_hardcodes_domain_statuses(queue_service):
    # 客户端即便传了 statuses，服务端也硬注入待办域三态
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a", statuses=("executed",)), page_size=100
    )
    assert page.total == 5
    assert all(i.decision.status.value != "executed" for i in page.items)


@pytest.mark.asyncio
async def test_queue_sort_by_confidence_asc(queue_service):
    queue_service.store.records.append(_record(hours_ago=9, confidence=0.9))
    queue_service.store.records.append(_record(hours_ago=10, confidence=0.2))
    page = await queue_service.list_pending(
        DecisionQuery(workspace_id="ws-a"), group="to_resolve", sort_by="confidence_asc"
    )
    confidences = [i.decision.confidence for i in page.items]
    assert confidences == sorted(confidences)
    assert confidences[-1] == 0.9
