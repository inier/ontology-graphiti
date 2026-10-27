"""T2 `DecisionRecord` 扩展字段与状态矩阵单元测试（E33/E34）

锁定三件事：
1. 新增字段 `status` / `entry_source` / `recommended_action` / `resolution` /
   `status_assumed` 能图节点往返（`to_node_properties` -> `from_node_properties`）
2. 缺失字段读取回落默认值（迁移未跑也不 500）
3. `status × outcome` 六乘五 = 30 组合：7 合法放行、23 非法**写侧拒绝**；
   读侧只告警不抛错（模型要从图节点反序列化，硬校验会让历史脏数据把列表打成 500）
4. 写侧异常**不得**是 `ValueError` 子类：`ExceptionHandlerMiddleware` 把 `ValueError`
   统一映射成 400 + `{"error": {...}}` 信封，而 `pydantic.ValidationError` 本身
   就是 `ValueError` 子类——沿用旧类型会让非法组合返回一套前端读不懂的信封
"""

import itertools
import json

import pytest

from odap.biz.decision.decision_record.models import (
    DecisionEntrySource,
    DecisionOutcome,
    DecisionRecord,
    DecisionStatus,
)
from odap.biz.decision.decision_record.models.status_matrix import (
    LEGAL_OUTCOMES,
    DecisionInvariantError,
    StatusOutcomePatch,
    assert_legal,
    reconcile_on_read,
)

# 界面标签真值（前端 `toDisplayLabel` 的同构副本）。
# 服务端不返回中文标签，故仅在本测试里用来验证"每个 outcome 只对应一个标签"。
FRONTEND_LABEL = {
    ("pending", None): "待裁定",
    ("decided", None): "待执行确认",
    ("executing", None): "待执行确认",
    ("executed", "success"): "执行成功",
    ("executed", "partial_success"): "部分成功",
    ("failed", "failure"): "执行失败",
    ("rejected", "rejected"): "已驳回",
}
# 终态 outcome 必须一一对应单个标签；`pending` 允许两种（待裁定 / 待执行确认）
TERMINAL_OUTCOMES = ("success", "partial_success", "failure", "rejected")

LOCAL = DecisionRecord(workspace_id="ws-a", context_summary="测试决策")


# ---------------- 枚举值域（与 api-spec 对齐） ----------------


def test_status_has_six_values():
    assert [s.value for s in DecisionStatus] == [
        "pending", "decided", "executing", "executed", "failed", "rejected",
    ]


def test_entry_source_has_seven_values():
    assert [s.value for s in DecisionEntrySource] == [
        "manual", "pipeline", "recommendation", "qa", "agent", "import", "legacy",
    ]


def test_outcome_five_values_unchanged():
    assert [o.value for o in DecisionOutcome] == [
        "success", "partial_success", "failure", "pending", "rejected",
    ]


def test_defaults_are_backward_compatible():
    assert LOCAL.status is DecisionStatus.PENDING
    assert LOCAL.entry_source is DecisionEntrySource.MANUAL
    assert LOCAL.recommended_action is None
    assert LOCAL.resolution is None
    assert LOCAL.status_assumed is False


# ---------------- 图节点往返 ----------------


def _full_record() -> DecisionRecord:
    return DecisionRecord(
        workspace_id="ws-a",
        context_summary="供应商漂移",
        evidence_entity_ids=["ent_1", "ent_2", "ent_3"],
        status=DecisionStatus.DECIDED,
        entry_source=DecisionEntrySource.PIPELINE,
        recommended_action={
            "action_type_id": "freeze_settlement",
            "target_object_id": "ent_8f21",
            "target_object_type": "Supplier",
            "parameters": {"reason": "semantic_drift"},
        },
        resolution={
            "action": "approve",
            "actor_type": "user",
            "by": "张三",
            "at": "2026-10-24T10:00:00+00:00",
            "reason": "",
        },
        status_assumed=False,
    )


def test_round_trip_preserves_new_fields():
    record = _full_record()
    restored = DecisionRecord.from_node_properties(record.to_node_properties())

    assert restored.status is DecisionStatus.DECIDED
    assert restored.entry_source is DecisionEntrySource.PIPELINE
    assert restored.recommended_action["target_object_type"] == "Supplier"
    assert restored.recommended_action["parameters"] == {"reason": "semantic_drift"}
    assert restored.resolution["actor_type"] == "user"
    assert restored.resolution["by"] == "张三"
    assert restored.status_assumed is False


def test_node_properties_exports_evidence_count():
    props = _full_record().to_node_properties()
    # 排序键 evidence_count 需要数值属性（JSON 字符串上 size() 无效）
    assert props["evidence_count"] == 3


def test_node_properties_exports_status_values_as_strings():
    props = _full_record().to_node_properties()
    assert props["status"] == "decided"
    assert props["entry_source"] == "pipeline"
    assert props["status_assumed"] is False


def test_from_node_properties_falls_back_when_fields_missing():
    # 迁移未跑的历史节点：只有老字段
    restored = DecisionRecord.from_node_properties(
        {"uuid": "dec_aaaaaaaaaaaa", "group_id": "ws-a", "outcome": "success"}
    )
    assert restored.status_assumed is False
    assert restored.entry_source is DecisionEntrySource.LEGACY
    assert restored.status is DecisionStatus.PENDING  # 读侧默认不猜流程状态


def test_from_node_properties_tolerates_unknown_status():
    restored = DecisionRecord.from_node_properties(
        {"uuid": "dec_bbbbbbbbbbbb", "group_id": "ws-a", "status": "weird_state"}
    )
    assert restored.status is DecisionStatus.PENDING


# ---------------- 矩阵：写侧拒绝 ----------------


def test_legal_outcomes_matrix_has_seven_combos():
    # 6×5=30；合法 7（pending/decided/executing 各 1 + executed 2 + failed 1 + rejected 1）
    total = sum(len(v) for v in LEGAL_OUTCOMES.values())
    assert total == 7


@pytest.mark.parametrize(
    "status,outcome",
    [(s, o) for s, outs in LEGAL_OUTCOMES.items() for o in sorted(outs)],
)
def test_legal_combos_pass_write_validation(status, outcome):
    patch = StatusOutcomePatch(status=status, outcome=outcome)
    assert patch.to_node_patch()["status"] == status


ILLEGAL_PAIRS = [
    (s, o)
    for s, o in itertools.product(
        [st.value for st in DecisionStatus], [oc.value for oc in DecisionOutcome]
    )
    if o not in LEGAL_OUTCOMES[s]
]


def test_illegal_pairs_count_is_twenty_three():
    # 6×5=30 组合，合法 7 个（pending/decided/executing 各 1 + executed 2 + failed 1 + rejected 1）
    assert len(ILLEGAL_PAIRS) == 23


@pytest.mark.parametrize("status,outcome", ILLEGAL_PAIRS)
def test_illegal_combos_are_rejected_on_write(status, outcome):
    with pytest.raises(DecisionInvariantError):
        StatusOutcomePatch(status=status, outcome=outcome)
    with pytest.raises(DecisionInvariantError):
        assert_legal(status, outcome)


def test_write_side_error_is_not_value_error():
    """`ValidationError` 是 `ValueError` 子类，而中间件把 `ValueError` 映射成 400。

    写侧异常必须是独立类型，否则非法组合会以 400 + 另一套信封返回。
    """
    assert not issubclass(DecisionInvariantError, ValueError)
    with pytest.raises(DecisionInvariantError):
        StatusOutcomePatch(status="executed", outcome="failure")


def test_flagship_illegal_combo_executed_with_pending_outcome():
    # status=executed 但 outcome=pending：台账会显示"执行成功"却"结果待定"
    with pytest.raises(DecisionInvariantError):
        assert_legal("executed", "pending")


def test_flagship_illegal_combo_executed_with_failure():
    with pytest.raises(DecisionInvariantError):
        assert_legal("executed", "failure")
    with pytest.raises(DecisionInvariantError):
        StatusOutcomePatch(status="executed", outcome="failure")


def test_flagship_illegal_combo_failed_with_partial_success():
    # 回滚/失败就是 failure。「失败但部分成功」会让「部分成功」这一个标签
    # 同时来自 executed 和 failed 两条路径，前端双参映射立刻歧义。
    with pytest.raises(DecisionInvariantError):
        assert_legal("failed", "partial_success")
    with pytest.raises(DecisionInvariantError):
        StatusOutcomePatch(status="failed", outcome="partial_success")


def test_failed_partial_success_not_in_legal_set():
    """正向断言：防止以后有人"顺手"把 partial_success 加回 failed。"""
    assert "partial_success" not in LEGAL_OUTCOMES["failed"]
    assert LEGAL_OUTCOMES["failed"] == frozenset({"failure"})


def _label(status: str, outcome: str) -> str:
    """按前端 `toDisplayLabel` 的双参语义取标签（status 优先，其次 status+outcome）。"""
    return FRONTEND_LABEL.get((status, None)) or FRONTEND_LABEL[(status, outcome)]


@pytest.mark.parametrize("outcome", TERMINAL_OUTCOMES)
def test_each_terminal_outcome_maps_to_single_label(outcome):
    """反向一致性：同一个 terminal outcome 只能渲染出一个标签。

    把 `partial_success` 加回 `failed` 会让本用例立刻变红——这正是它存在的理由。
    """
    labels = {
        _label(status, outcome)
        for status, allowed in LEGAL_OUTCOMES.items()
        if outcome in allowed
    }
    assert len(labels) == 1, f"outcome={outcome} 对应多个界面标签: {sorted(labels)}"


def test_rolled_back_maps_to_failed_failure():
    """`rolled_back` 的落点是 failed + failure，不是 executed + partial_success。"""
    patch = StatusOutcomePatch(
        status="failed",
        outcome="failure",
        details={"action_status": "rolled_back", "rolled_back_items": ["推荐动作 A"]},
    )
    node_patch = patch.to_node_patch()
    assert node_patch["status"] == "failed"
    assert node_patch["outcome"] == "failure"
    # details 进 outcome_details（JSON 字符串），不摊平成节点顶层属性：
    # 摊平会覆盖节点既有属性，且读侧只从 outcome_details 取这些键
    details = json.loads(node_patch["outcome_details"])
    assert details["action_status"] == "rolled_back"
    assert details["rolled_back_items"] == ["推荐动作 A"]


def test_patch_is_single_atomic_payload():
    patch = StatusOutcomePatch(
        status="executed", outcome="partial_success", details={"action_status": "succeeded"}
    )
    node_patch = patch.to_node_patch()
    # status 与 outcome 必须同一次写入，不可是两个 patch
    assert node_patch["status"] == "executed"
    assert node_patch["outcome"] == "partial_success"
    assert json.loads(node_patch["outcome_details"])["action_status"] == "succeeded"
    assert "updated_at" in node_patch


def test_patch_cannot_overwrite_node_identity():
    """客户端塞进 details 的主键字段不得成为节点顶层属性。"""
    patch = StatusOutcomePatch(
        status="decided", outcome="pending", details={"decision_id": "dec_evil", "group_id": "ws-b"}
    )
    node_patch = patch.to_node_patch()
    assert "decision_id" not in node_patch
    assert "group_id" not in node_patch


# ---------------- 矩阵：读侧只告警 ----------------


def test_read_side_warns_but_does_not_raise(caplog):
    props = {
        "uuid": "dec_cccccccccccc",
        "group_id": "ws-a",
        "status": "executed",
        "outcome": "pending",
    }
    with caplog.at_level("WARNING"):
        record = DecisionRecord.from_node_properties(props)

    assert record.status is DecisionStatus.EXECUTED  # 冲突时以流程位置为准
    assert record.outcome is DecisionOutcome.PENDING
    assert any("status" in r.message and "outcome" in r.message for r in caplog.records)


def test_reconcile_on_read_returns_reason_for_conflict():
    assert reconcile_on_read("executed", "pending") is not None
    assert reconcile_on_read("decided", "pending") is None
