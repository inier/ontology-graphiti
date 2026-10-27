"""T4/T5 决策台账：状态机 / SLA 阈值 / 台账分页单测

队列（分组 + 四计数 + 分档 SLA）见 `test_decision_queue.py`。
不使用 Neo4j：`InMemoryDecisionStore` 按 `DecisionQuery` 做真实筛选、排序、分页，
从而验证"分组与计数同源"这类契约级不变量。
"""

from datetime import datetime, timedelta, timezone

import pytest

from odap.biz.decision.decision_hub.services.ledger_service import LedgerService
from odap.biz.decision.decision_hub.services.sla import sla_bounds, sla_state
from odap.biz.decision.decision_hub.services.state_machine import (
    GROUP_STATUSES,
    available_operations,
    derive_group,
)
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
    workspace_id: str = "ws-a",
    **kwargs,
) -> DecisionRecord:
    created = NOW - timedelta(hours=hours_ago)
    return DecisionRecord(
        workspace_id=workspace_id,
        context_summary=kwargs.pop("context_summary", "供应商主数据漂移"),
        status=status,
        outcome=outcome,
        created_at=created,
        updated_at=created,
        valid_at=created,
        **kwargs,
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.fixture
def service():
    store = InMemoryDecisionStore()
    return LedgerService(store=store, now_provider=lambda: NOW)


# ---------------- 状态机 ----------------


@pytest.mark.parametrize(
    "status,expected",
    [
        ("pending", ["approve", "reject"]),
        ("decided", ["execute"]),
        ("failed", ["retry"]),
        ("executing", []),
        ("executed", []),
        ("rejected", []),
    ],
)
def test_available_operations_single_source(status, expected):
    assert available_operations(status) == expected


@pytest.mark.parametrize(
    "status,expected",
    [("pending", "to_resolve"), ("decided", "to_execute"), ("executing", "to_execute")],
)
def test_derive_group(status, expected):
    assert derive_group(status) == expected


@pytest.mark.parametrize("status", ["executed", "failed", "rejected"])
def test_terminal_status_not_in_queue(status):
    assert derive_group(status) is None


def test_queue_domain_is_three_statuses():
    assert set(GROUP_STATUSES) == {"to_resolve", "to_execute"}
    union = {s for group in GROUP_STATUSES.values() for s in group}
    assert union == {"pending", "decided", "executing"}


def test_group_and_domain_are_consistent():
    # 分组取值必须恰好覆盖待办域，不允许"域里有但分组里没有"的漏项
    for status in {s for group in GROUP_STATUSES.values() for s in group}:
        assert derive_group(status) in GROUP_STATUSES


# ---------------- SLA ----------------


@pytest.mark.parametrize(
    "minutes,expected",
    [(0, "ok"), (1439, "ok"), (1440, "ok"), (1441, "warning"), (4320, "warning"),
     (4321, "breached"), (99999, "breached")],
)
def test_sla_state_thresholds(minutes, expected):
    assert sla_state(minutes) == expected


def test_sla_bounds_are_derived_from_thresholds():
    warning_from, warning_to, breached_to = sla_bounds(NOW)
    assert _dt(warning_from) == NOW - timedelta(hours=72)
    assert _dt(warning_to) == NOW - timedelta(hours=24)
    assert _dt(breached_to) == NOW - timedelta(hours=72)


def test_sla_thresholds_are_configurable_via_env(monkeypatch):
    monkeypatch.setenv("ODAP_SLA_WARNING_MINUTES", "60")
    monkeypatch.setenv("ODAP_SLA_BREACH_MINUTES", "120")
    assert sla_state(61) == "warning"
    assert sla_state(121) == "breached"


# ---------------- 台账 ----------------


@pytest.mark.asyncio
async def test_ledger_paginates_and_reports_total(service):
    store = service.store
    for i in range(5):
        store.records.append(_record(hours_ago=i, context_summary=f"决策-{i}"))

    page = await service.list_ledger(DecisionQuery(workspace_id="ws-a", exclude_assumed=False), 2, 2)

    assert page.page == 2 and page.page_size == 2
    assert page.total == 5
    assert page.total_is_estimate is False
    assert page.has_more is True
    assert len(page.items) == 2


@pytest.mark.asyncio
async def test_ledger_has_more_false_on_last_page(service):
    for i in range(3):
        service.store.records.append(_record(hours_ago=i))
    page = await service.list_ledger(DecisionQuery(workspace_id="ws-a", exclude_assumed=False), 2, 2)
    assert page.has_more is False


@pytest.mark.asyncio
async def test_ledger_estimate_mode_uses_page_size_for_has_more(service):
    for i in range(8):
        service.store.records.append(_record(hours_ago=i))
    query = DecisionQuery(workspace_id="ws-a", exclude_assumed=False)
    # 模拟 store 估算态：total=3 但仍有下一页
    service.store.count_decisions = _estimate_counter(3, True)
    page = await service.list_ledger(query, 1, 3)
    assert page.total_is_estimate is True
    assert page.total == 3
    assert page.has_more is True


def _estimate_counter(total: int, is_estimate: bool):
    async def _counter(query, probe=5000):
        return total, is_estimate

    return _counter


@pytest.mark.asyncio
async def test_ledger_filters_by_workspace(service):
    service.store.records.append(_record(workspace_id="ws-a"))
    service.store.records.append(_record(workspace_id="ws-b"))
    page = await service.list_ledger(DecisionQuery(workspace_id="ws-a", exclude_assumed=False), 1, 20)
    assert page.total == 1
    assert page.items[0].workspace_id == "ws-a"
