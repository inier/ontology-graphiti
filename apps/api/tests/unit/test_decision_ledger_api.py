"""T5 台账 / 队列端点契约测试（TestClient + 内存 store）

直接按 api-spec 断言字段名与取值域，防止"接口 200 但组合起来是空的"：
- `total_is_estimate` / `has_more` 恒返回
- `page > 100`、`min_confidence > max_confidence` 返回 422
- `workspace_id` 只从 JWT 声明解析（查询串里的同名参数必须被忽略）
- 队列 `sla_state` 由后端派生，请求带 `sla_minutes` 不改变结果
- 跨空间数据不出现在任何响应中（列表类端点的隔离）
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.decision.decision_hub.api.routes import decision_hub_router
from odap.biz.decision.decision_hub.services.ledger_service import (
    LedgerService,
    get_ledger_service,
)
from odap.biz.decision.decision_record.models import (
    DecisionOutcome,
    DecisionRecord,
    DecisionStatus,
)
from odap.infra.security.jwt_auth import get_current_user

from decision_fakes import InMemoryDecisionStore

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _record(hours_ago: float = 1, workspace_id: str = "ws-a", **kwargs) -> DecisionRecord:
    created = NOW - timedelta(hours=hours_ago)
    kwargs.setdefault("status", DecisionStatus.PENDING)
    return DecisionRecord(
        workspace_id=workspace_id,
        context_summary=kwargs.pop("context_summary", "供应商主数据漂移"),
        created_at=created,
        updated_at=created,
        valid_at=created,
        **kwargs,
    )


def _resolution(hours_ago: float) -> dict:
    """裁决留痕（`at` 决定 to_execute 档的 SLA 计时起点）。"""
    return {
        "action": "approve",
        "actor_type": "user",
        "by": "张三",
        "at": (NOW - timedelta(hours=hours_ago)).isoformat(),
        "reason": "",
    }


@pytest.fixture
def store() -> InMemoryDecisionStore:
    return InMemoryDecisionStore(
        [
            _record(hours_ago=1, context_summary="漂移-1", confidence=0.4),
            _record(hours_ago=30, context_summary="漂移-2", confidence=0.8, evidence_entity_ids=["e1"]),
            _record(hours_ago=100, context_summary="漂移-3"),
            _record(hours_ago=2, status=DecisionStatus.DECIDED, resolution=_resolution(1)),
            _record(hours_ago=3, status=DecisionStatus.EXECUTING, resolution=_resolution(2)),
            _record(hours_ago=4, status=DecisionStatus.EXECUTED, outcome=DecisionOutcome.SUCCESS),
            # 其他空间的记录：任何响应里都不许出现
            _record(hours_ago=1, workspace_id="ws-b", context_summary="别人的决策"),
        ]
    )


@pytest.fixture
def client(store) -> TestClient:
    app = FastAPI()
    app.include_router(decision_hub_router)
    app.dependency_overrides[get_ledger_service] = lambda: LedgerService(
        store=store, now_provider=lambda: NOW
    )

    async def _user():
        return {"sub": "u1", "name": "analyst", "role": "analyst", "ws_id": "ws-a"}

    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def _drop_ws_claim(client: TestClient) -> None:
    async def _user_without_ws():
        return {"sub": "u1", "role": "analyst"}

    client.app.dependency_overrides[get_current_user] = _user_without_ws


# ---------------- 台账 ----------------


def test_ledger_returns_contract_fields(client):
    resp = client.get("/api/decisions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("items", "total", "total_is_estimate", "page", "page_size", "has_more"):
        assert key in body
    assert body["page"] == 1 and body["page_size"] == 20
    assert body["total_is_estimate"] is False


def test_ledger_excludes_other_workspace(client, store):
    body = client.get("/api/decisions").json()
    assert body["total"] == 6  # ws-a 6 条，ws-b 那条不可见
    assert all(item["workspace_id"] == "ws-a" for item in body["items"])
    assert all(item["context_summary"] != "别人的决策" for item in body["items"])


def test_ledger_ignores_client_supplied_workspace(client, store):
    client.get("/api/decisions", params={"workspace_id": "ws-b"})
    query = store.list_calls[-1][0]
    assert query.workspace_id == "ws-a"  # 只认 JWT 声明


def test_ledger_rejects_page_over_limit(client):
    assert client.get("/api/decisions", params={"page": 101}).status_code == 422


def test_ledger_rejects_min_greater_than_max_confidence(client):
    resp = client.get("/api/decisions", params={"min_confidence": 0.9, "max_confidence": 0.1})
    assert resp.status_code == 422


def test_ledger_multi_value_status_and_outcome(client, store):
    resp = client.get(
        "/api/decisions",
        params=[
            ("status", "executed"),
            ("status", "failed"),
            ("outcome", "success"),
            ("outcome", "partial_success"),
        ],
    )
    assert resp.status_code == 200
    query = store.list_calls[-1][0]
    assert query.statuses == ("executed", "failed")
    assert query.outcomes == ("success", "partial_success")


def test_ledger_filters_by_agent_id_and_entry_source(client, store):
    client.get("/api/decisions", params={"agent_id": "agent-7", "entry_source": "qa"})
    query = store.list_calls[-1][0]
    assert query.agent_id == "agent-7"
    assert query.entry_source == "qa"


def test_ledger_rejects_removed_evidence_count_sort(client):
    # 契约 v1.2.0 物理删除 evidence_count 排序（需写时派生 + M3 回填，降 P1）。
    # 留着枚举位会让前端拿到"Literal 接受但行为未定义"的结果，比 422 更难排查。
    assert client.get("/api/decisions", params={"sort": "evidence_count"}).status_code == 422


def test_ledger_rejects_unknown_sort(client):
    assert client.get("/api/decisions", params={"sort": "uuid"}).status_code == 422


def test_ledger_missing_workspace_claim_is_422(client):
    _drop_ws_claim(client)
    resp = client.get("/api/decisions")
    assert resp.status_code == 422


def test_ledger_estimate_mode(client, store):
    async def _estimate(query, probe=5000):
        return 5000, True

    store.count_decisions = _estimate
    body = client.get("/api/decisions", params={"page_size": 2}).json()
    assert body["total"] == 5000
    assert body["total_is_estimate"] is True
    assert body["has_more"] is True  # 取满一页即认为还有下一页


def test_ledger_query_is_passed_created_range(client, store):
    client.get(
        "/api/decisions",
        params={"created_from": "2026-10-01T00:00:00Z", "created_to": "2026-10-31T00:00:00Z"},
    )
    query = store.list_calls[-1][0]
    assert query.created_from.startswith("2026-10-01T00:00:00.000000")
    assert query.created_to.startswith("2026-10-31T00:00:00.000000")


# ---------------- 待决策队列 ----------------


def test_pending_returns_groups_and_counts(client):
    resp = client.get("/api/decisions/pending")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["counts"]) == {"to_resolve", "to_execute", "sla_warning", "sla_breached"}
    assert body["total"] == body["counts"]["to_resolve"] + body["counts"]["to_execute"]
    assert {item["group"] for item in body["items"]} == {"to_resolve", "to_execute"}


def test_pending_item_fields_match_contract(client):
    item = client.get("/api/decisions/pending").json()["items"][0]
    for key in ("decision", "group", "waited_minutes", "decided_waited_minutes",
                "sla_state", "available_operations", "executable"):
        assert key in item
    assert item["sla_state"] in ("ok", "warning", "breached")


def test_pending_item_has_no_evidence_count(client):
    # 契约 v1.2.0 已从 PendingDecisionItem 移除该字段
    item = client.get("/api/decisions/pending").json()["items"][0]
    assert "evidence_count" not in item


def test_pending_rejects_removed_evidence_count_sort(client):
    resp = client.get("/api/decisions/pending", params={"sort_by": "evidence_count_asc"})
    assert resp.status_code == 422


def test_pending_decided_waited_minutes_only_for_to_execute(client):
    items = client.get("/api/decisions/pending", params={"page_size": 100}).json()["items"]
    for item in items:
        if item["group"] == "to_resolve":
            assert item["decided_waited_minutes"] is None
        else:
            assert isinstance(item["decided_waited_minutes"], int)


def test_ledger_partial_success_filter_is_label_consistent(client, store):
    """反例断言：以 outcome=partial_success 筛选，返回行必须全是 executed（=部分成功）。

    矩阵若把 partial_success 放回 failed，这一行会立刻变红——它测的是
    "用户按什么筛选就该看到什么"，而不是守门员是否尽职。
    """
    store.records.append(
        _record(hours_ago=6, status=DecisionStatus.EXECUTED,
                outcome=DecisionOutcome.PARTIAL_SUCCESS)
    )
    body = client.get("/api/decisions", params={"outcome": "partial_success"}).json()
    assert body["items"]
    assert {item["status"] for item in body["items"]} == {"executed"}


def test_pending_sla_states_are_derived_server_side(client):
    items = client.get("/api/decisions/pending").json()["items"]
    by_wait = {i["waited_minutes"]: i["sla_state"] for i in items}
    assert by_wait[60] == "ok"
    assert by_wait[1800] == "warning"
    assert by_wait[6000] == "breached"


def test_pending_ignores_client_sla_override(client):
    baseline = client.get("/api/decisions/pending").json()
    tampered = client.get(
        "/api/decisions/pending", params={"sla_minutes": 99999, "status": "executed"}
    ).json()
    assert tampered["total"] == baseline["total"]
    assert tampered["counts"] == baseline["counts"]
    assert {i["sla_state"] for i in tampered["items"]} == {
        i["sla_state"] for i in baseline["items"]
    }


def test_pending_group_filter(client):
    body = client.get("/api/decisions/pending", params={"group": "to_execute"}).json()
    assert {item["group"] for item in body["items"]} == {"to_execute"}
    assert body["counts"]["to_resolve"] == 3  # 计数不受 group 收窄影响


def test_pending_missing_workspace_claim_is_422(client):
    _drop_ws_claim(client)
    assert client.get("/api/decisions/pending").status_code == 422


def test_pending_rejects_unknown_group(client):
    assert client.get("/api/decisions/pending", params={"group": "to_done"}).status_code == 422


def test_pending_excludes_legacy_assumed_records(client, store):
    store.records.extend([_record(hours_ago=5, status_assumed=True) for _ in range(3)])
    body = client.get("/api/decisions/pending").json()
    assert body["total"] == 5
