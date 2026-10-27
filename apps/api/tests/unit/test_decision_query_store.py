"""T3 决策存储读侧单测：查询对象 / Cypher 参数构造 / 存量迁移幂等

不依赖 Neo4j 连接：Cypher 只测"参数与白名单分支"这些纯逻辑，
迁移用行为级 Fake driver（按 WHERE 守卫过滤节点）证明二次运行 0 行。
"""

import json
from datetime import datetime, timezone

import pytest

from odap.biz.decision.decision_record.impl.decision_query_cypher import (
    build_params,
    order_clause,
)
from odap.biz.decision.decision_record.impl.neo4j_decision_migration import (
    Neo4jDecisionMigrationMixin,
    derive_legacy_fields,
)
from odap.biz.decision.decision_record.impl.neo4j_decision_query import Neo4jDecisionQueryMixin
from odap.biz.decision.decision_record.interfaces.decision_query import DecisionQuery


# ---------------- DecisionQuery ----------------


def test_query_defaults_are_safe():
    query = DecisionQuery(workspace_id="ws-a")
    # 危险值作默认：漏传 exclude_assumed 只会让队列少几条历史假数据
    assert query.exclude_assumed is True
    assert query.statuses == ()
    assert query.outcomes == ()
    assert query.sort_by == "created_at"
    assert query.order == "desc"


def test_query_is_immutable():
    query = DecisionQuery(workspace_id="ws-a")
    with pytest.raises(Exception):
        query.workspace_id = "ws-b"  # type: ignore[misc]


def test_query_replace_keeps_other_fields():
    from dataclasses import replace

    base = DecisionQuery(workspace_id="ws-a", entry_source="qa")
    narrowed = replace(base, statuses=("pending",))
    assert narrowed.statuses == ("pending",)
    assert narrowed.entry_source == "qa"
    assert narrowed.workspace_id == "ws-a"


# ---------------- Cypher 参数构造 ----------------


def test_build_params_short_circuits_none_filters():
    params = build_params(DecisionQuery(workspace_id="ws-a"))
    assert params["ws"] == "ws-a"
    assert params["statuses"] == []          # 空列表 => WHERE 短路
    assert params["outcomes"] == []
    assert params["entry_source"] is None
    assert params["q"] is None
    assert params["exclude_assumed"] is True


def test_build_params_maps_multi_value_and_ranges():
    query = DecisionQuery(
        workspace_id="ws-a",
        statuses=("executed", "failed"),
        outcomes=("success", "partial_success"),
        entry_source="pipeline",
        agent_id="agent-1",
        min_confidence=0.3,
        max_confidence=0.9,
        text_query="漂移",
        created_from="2026-10-01T00:00:00.000000+00:00",
        created_to="2026-10-31T00:00:00.000000+00:00",
        exclude_assumed=False,
    )
    params = build_params(query)
    assert params["statuses"] == ["executed", "failed"]
    assert params["outcomes"] == ["success", "partial_success"]
    assert params["entry_source"] == "pipeline"
    assert params["agent_id"] == "agent-1"
    assert params["min_conf"] == 0.3
    assert params["max_conf"] == 0.9
    assert params["q"] == "漂移"
    assert params["from"] == "2026-10-01T00:00:00.000000+00:00"
    assert params["to"] == "2026-10-31T00:00:00.000000+00:00"
    assert params["exclude_assumed"] is False


@pytest.mark.parametrize(
    "sort_by,order,expected",
    [
        ("created_at", "desc", "n.created_at DESC"),
        ("created_at", "asc", "n.created_at ASC"),
        ("updated_at", "desc", "n.updated_at DESC"),
        ("confidence", "asc", "coalesce(n.confidence, 0) ASC"),
        ("evidence_count", "desc", "coalesce(n.evidence_count, 0) DESC"),
    ],
)
def test_order_clause_whitelist(sort_by, order, expected):
    assert order_clause(sort_by, order) == expected


@pytest.mark.parametrize("sort_by", ["n.created_at", "created_at; DROP", "uuid"])
def test_order_clause_rejects_unknown_sort(sort_by):
    # 防注入：排序键只能来自白名单，绝不拼接客户端原值
    with pytest.raises(ValueError):
        order_clause(sort_by, "desc")


def test_order_clause_rejects_unknown_order():
    with pytest.raises(ValueError):
        order_clause("created_at", "sideways")


# ---------------- 存量回填规则表（§4.3 五行） ----------------


@pytest.mark.parametrize(
    "props,expected_status,expected_assumed",
    [
        ({"outcome": "success"}, "executed", False),
        ({"outcome": "partial_success"}, "executed", False),
        ({"outcome": "failure"}, "failed", False),
        ({"outcome": "rejected"}, "rejected", False),
        ({"outcome": "pending", "outcome_details": '{"action_status": "executing"}'}, "executing", False),
        # 无 outcome 且无执行痕迹：无法判定 => pending + 推定标记，不进队列
        ({"outcome": None}, "pending", True),
        ({"outcome": "pending"}, "pending", True),
        ({}, "pending", True),
    ],
)
def test_derive_legacy_fields_rule_table(props, expected_status, expected_assumed):
    patch = derive_legacy_fields({**props, "uuid": "dec_aaaaaaaaaaaa"})
    assert patch["status"] == expected_status
    assert patch["status_assumed"] is expected_assumed
    assert patch["entry_source"] == "legacy"


def test_derive_legacy_fields_reads_outcome_details_as_dict():
    # 图上存的是 JSON 字符串，但 dict 也须识别，避免规则静默失效
    patch = derive_legacy_fields(
        {"outcome": "pending", "outcome_details": {"action_status": "completed"}}
    )
    assert patch["status"] == "executing"
    assert patch["status_assumed"] is False


def test_derive_legacy_fields_keeps_existing_entry_source():
    patch = derive_legacy_fields({"outcome": "success", "entry_source": "pipeline"})
    assert patch["entry_source"] == "pipeline"


def test_derive_legacy_fields_normalizes_temporal_types():
    # M1：created_at 若不是字符串，范围过滤与排序索引都会失效
    dt = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    patch = derive_legacy_fields({"outcome": "success", "created_at": dt})
    assert patch["created_at"] == "2026-10-01T12:00:00.000000+00:00"
    assert patch["updated_at"] == "2026-10-01T12:00:00.000000+00:00"


def test_derive_legacy_fields_backfills_evidence_count():
    patch = derive_legacy_fields(
        {"outcome": "success", "evidence_entity_ids": json.dumps(["e1", "e2"])}
    )
    assert patch["evidence_count"] == 2


def test_derive_legacy_fields_skips_present_evidence_count():
    patch = derive_legacy_fields({"outcome": "success", "evidence_count": 7})
    assert "evidence_count" not in patch


# ---------------- 迁移幂等（行为级 Fake driver） ----------------


class _FakeRows(list):
    pass


class _FakeDriver:
    """最小行为级 Fake：按 WHERE 守卫过滤节点，可验证幂等。"""

    def __init__(self, nodes):
        self.nodes = nodes
        self.queries = []

    async def execute_query(self, cypher, **kwargs):
        self.queries.append((cypher, kwargs))
        if "RETURN n LIMIT" in cypher or "RETURN n ORDER BY" in cypher:
            return _FakeRows([{"n": dict(n)} for n in self._matching(cypher)]), None, None
        if "SET n +=" in cypher:
            return _FakeRows(self._apply(cypher, kwargs)), None, None
        if "RETURN count(n) AS c" in cypher:
            return _FakeRows([{"c": len(self._matching(cypher))}]), None, None
        return _FakeRows([]), None, None

    def _matching(self, cypher):
        if "n.status IS NULL" in cypher:
            return [n for n in self.nodes if n.get("status") is None]
        if "n.evidence_count IS NULL" in cypher:
            return [
                n for n in self.nodes
                if n.get("status") is not None and n.get("evidence_count") is None
            ]
        return list(self.nodes)

    def _apply(self, cypher, kwargs):
        """模拟 `WHERE guard SET n += $patch RETURN n.uuid`：守卫不满足则 0 行。"""
        guard_ok = any(n.get("uuid") == kwargs.get("uuid") for n in self._matching(cypher))
        if not guard_ok:
            return []
        for node in self.nodes:
            if node.get("uuid") == kwargs.get("uuid"):
                node.update(kwargs.get("patch") or {})
                return [{"uuid": node["uuid"]}]
        return []


@pytest.fixture
def fake_driver(monkeypatch):
    nodes = [
        {"uuid": "dec_111111111111", "group_id": "ws-a", "outcome": "success",
         "evidence_entity_ids": json.dumps(["e1"])},
        {"uuid": "dec_222222222222", "group_id": "ws-a", "outcome": None},
        {"uuid": "dec_333333333333", "group_id": "ws-a", "outcome": "pending",
         "outcome_details": json.dumps({"action_status": "executing"})},
    ]
    driver = _FakeDriver(nodes)
    import odap.biz.decision.decision_record.impl.neo4j_driver as driver_module

    monkeypatch.setattr(driver_module, "get_decision_driver", lambda: driver)
    return driver


class _Store(Neo4jDecisionMigrationMixin, Neo4jDecisionQueryMixin):
    pass


@pytest.mark.asyncio
async def test_migration_first_run_backfills_all(fake_driver):
    result = await _Store().migrate_legacy_fields()
    assert result["migrated_status"] == 3
    by_uuid = {n["uuid"]: n for n in fake_driver.nodes}
    assert by_uuid["dec_111111111111"]["status"] == "executed"
    assert by_uuid["dec_222222222222"]["status"] == "pending"
    assert by_uuid["dec_222222222222"]["status_assumed"] is True
    assert by_uuid["dec_333333333333"]["status"] == "executing"


@pytest.mark.asyncio
async def test_migration_is_idempotent_second_run_zero_rows(fake_driver):
    store = _Store()
    await store.migrate_legacy_fields()
    second = await store.migrate_legacy_fields()
    assert second["migrated_status"] == 0
    assert second["migrated_evidence_count"] == 0


@pytest.mark.asyncio
async def test_migration_never_queues_legacy_records(fake_driver):
    await _Store().migrate_legacy_fields()
    legacy = next(n for n in fake_driver.nodes if n["uuid"] == "dec_222222222222")
    # 数据层就不满足队列条件：不靠前端过滤
    assert legacy["status"] == "pending"
    assert legacy["status_assumed"] is True
    assert legacy["entry_source"] == "legacy"


@pytest.mark.asyncio
async def test_list_decisions_returns_models(fake_driver):
    fake_driver.nodes[0]["status"] = "executed"
    fake_driver.nodes[0]["workspace_id"] = "ws-a"
    rows = await _Store().list_decisions(DecisionQuery(workspace_id="ws-a"), skip=0, limit=10)
    assert len(rows) == 3
    assert rows[0].decision_id == "dec_111111111111"
    assert rows[0].status.value == "executed"
