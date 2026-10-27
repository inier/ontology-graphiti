"""决策结果回填映射（§5.3 映射表 / G3「回滚被记成结果待定」）

`_backfill_decision_outcome` 是 outcome 的**唯一回填出口**，故映射表单独成模块，
让 8 个 `ActionRequestStatus` 各自落到哪儿能被逐行对照，而不是散在 if/elif 里。

重点回归：`rolled_back` 曾掉进 `else` 被写成 `outcome=pending`，于是同一个
`pending` 同时表示"还没人裁决""正在执行""跑到一半回滚了"三件事。
现落 `failure`，部分达成的事实进 `outcome_details`（不占 `outcome` 枚举——
一个枚举值只能对应一个界面标签）。
"""

from types import SimpleNamespace

import pytest

from odap.biz.decision.decision_pipeline.outcome_mapping import (
    IN_FLIGHT_OUTCOME,
    outcome_for,
    rollback_items,
    status_for,
)

IN_FLIGHT_STATUSES = ("pending", "validating", "approved", "executing")


@pytest.mark.parametrize(
    "status,expected",
    [
        ("completed", "success"),
        ("rejected", "rejected"),
        ("failed", "failure"),
        ("rolled_back", "failure"),
    ],
)
def test_terminal_status_mapping(status, expected):
    assert outcome_for(status) == expected


def test_rolled_back_is_failure_not_pending():
    """回滚是失败，不是"结果待定"（原实现掉进 else 的静默错误）。"""
    assert outcome_for("rolled_back") == "failure"
    assert outcome_for("rolled_back") != IN_FLIGHT_OUTCOME


@pytest.mark.parametrize("status", IN_FLIGHT_STATUSES)
def test_in_flight_statuses_stay_pending(status):
    assert outcome_for(status) == "pending"


def test_unknown_status_does_not_become_terminal():
    # 未知状态保守留在 pending：宁可"未定"也不能凭空宣布成功或失败
    assert outcome_for("something_new") == IN_FLIGHT_OUTCOME


def test_opa_rejection_without_action_record():
    assert outcome_for("", opa_approved=False, has_record=False) == "rejected"


def test_opa_rejection_with_action_record_keeps_action_status():
    # 有 action record 时以执行状态为准（OPA 通过后的路径）
    assert outcome_for("completed", opa_approved=False, has_record=True) == "success"


def test_rollback_items_single_target():
    details = rollback_items({"target_object_id": "ent_8f21"})
    assert details == {"achieved_items": [], "rolled_back_items": ["ent_8f21"]}


def test_rollback_items_from_parameters_batch():
    details = rollback_items(
        {"target_object_id": "batch_1", "parameters": {"items": ["obj_a", "obj_b"]}}
    )
    assert details["rolled_back_items"] == ["obj_a", "obj_b"]
    assert details["achieved_items"] == []


def test_rollback_items_tolerates_missing_target():
    assert rollback_items({}) == {"achieved_items": [], "rolled_back_items": []}


# ---------------- status 侧：与 outcome 同批写入 ----------------


@pytest.mark.parametrize(
    "action_status,outcome,expected",
    [
        ("completed", "success", "executed"),
        ("completed", "partial_success", "executed"),
        ("failed", "failure", "failed"),
        ("rolled_back", "failure", "failed"),
        ("rejected", "rejected", "rejected"),
        ("executing", "pending", "executing"),
        ("approved", "pending", "decided"),
        ("pending", "pending", "decided"),
        ("", "pending", "pending"),
    ],
)
def test_status_for_matches_matrix(action_status, outcome, expected):
    """回填产出的 (status, outcome) 必须落在 7 个合法组合内。"""
    from odap.biz.decision.decision_record.models.status_matrix import is_legal

    status = status_for(action_status, outcome, has_record=bool(action_status))
    assert status == expected
    assert is_legal(status, outcome), f"回填组合非法: {status}+{outcome}"


def test_status_for_reaised_rejection():
    assert status_for("", "rejected", has_record=False) == "rejected"


# ---------------- 出口函数集成 ----------------

@pytest.mark.asyncio
async def test_backfill_writes_failure_for_rolled_back(monkeypatch):
    """端到端断言：回滚落库的 (status, outcome) 必须是 failed + failure。"""
    from odap.biz.decision.decision_pipeline import pipeline as pipeline_mod

    captured = {}

    class _Service:
        async def update_decision_outcome(self, **kwargs):
            captured.update(kwargs)
            return True

    monkeypatch.setattr(
        "odap.biz.decision.decision_record.get_decision_service", lambda: _Service()
    )
    result = SimpleNamespace(
        decision=SimpleNamespace(decision_id="dec_1", opa_approved=True),
        action_record={"action_record_id": "ar_1", "status": "rolled_back",
                       "target_object_id": "ent_8f21"},
        feedback=None,
    )
    await pipeline_mod.DecisionPipeline.__new__(
        pipeline_mod.DecisionPipeline
    )._backfill_decision_outcome(result, "ws-a")

    patch = captured["patch"]
    assert patch.status.value == "failed"
    assert patch.outcome.value == "failure"
    assert patch.details["action_status"] == "rolled_back"
    assert patch.details["rolled_back_items"] == ["ent_8f21"]


@pytest.mark.asyncio
async def test_backfill_in_flight_keeps_pending_outcome(monkeypatch):
    """执行中回填不得写成终态：`executing + pending` 才是合法组合。"""
    from odap.biz.decision.decision_pipeline import pipeline as pipeline_mod

    captured = {}

    class _Service:
        async def update_decision_outcome(self, **kwargs):
            captured.update(kwargs)
            return True

    monkeypatch.setattr(
        "odap.biz.decision.decision_record.get_decision_service", lambda: _Service()
    )
    result = SimpleNamespace(
        decision=SimpleNamespace(decision_id="dec_2", opa_approved=True),
        action_record={"action_record_id": "ar_2", "status": "executing"},
        feedback=None,
    )
    await pipeline_mod.DecisionPipeline.__new__(
        pipeline_mod.DecisionPipeline
    )._backfill_decision_outcome(result, "ws-a")

    assert captured["patch"].status.value == "executing"
    assert captured["patch"].outcome.value == "pending"
