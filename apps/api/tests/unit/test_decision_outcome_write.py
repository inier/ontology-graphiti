"""状态写侧：单一 patch 出口 / 非法迁移 409 / 非法组合 500

三条硬约束（架构 §5.2.1 + team-lead 裁定）：
1. **写 `status` 的代码路径只有一条**：`StatusOutcomePatch.to_node_patch()` ->
   一次 `SET n += $patch`。散写（`SET n.status = ...`）会绕过 7/23 矩阵，
   也让 `updated_at` 出现多种写法——详情页「状态同步中」的窗口计时全靠它。
2. **非法迁移**（`pending -> executed`）是客户端可理解的冲突：409 +
   `error.code=illegal_transition`；不能落进 `except ValueError -> 422 str(e)`。
3. **非法 `status × outcome`** 是内部不变量被破坏：500，不是 409。
"""

import inspect
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.decision.decision_hub.services.state_machine import assert_transition
from odap.biz.decision.decision_record.api.routes import (
    OutcomeUpdate,
    decision_record_router,
)
from odap.biz.decision.decision_record.impl.neo4j_decision_store import Neo4jDecisionStore
from odap.biz.decision.decision_record.models import (
    DecisionOutcome,
    DecisionStatus,
)
from odap.biz.decision.decision_record.models.status_matrix import (
    DecisionInvariantError,
    StatusOutcomePatch,
)
from odap.infra.middleware.exception_handler import APIError, ConflictError
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.workspace_access import get_current_workspace

from decision_fakes import InMemoryDecisionStore


class _RecordingStore(InMemoryDecisionStore):
    """记录 `update_outcome` 收到的 patch，用来验证"一次写、写一份"。"""

    def __init__(self) -> None:
        super().__init__([])
        self.patches = []

    async def update_outcome(self, decision_id, workspace_id, patch, feedback_summary=None) -> bool:
        self.patches.append((decision_id, workspace_id, patch, feedback_summary))
        return True

    async def get_decision(self, decision_id: str, workspace_id: str):
        from odap.biz.decision.decision_record.models import DecisionRecord

        return DecisionRecord(decision_id=decision_id, workspace_id=workspace_id)


@pytest.fixture
def store():
    return _RecordingStore()


@pytest.fixture
def client(store, monkeypatch):
    from odap.biz.decision.decision_record import services as services_pkg

    service = services_pkg.DecisionService(store=store)
    app = FastAPI()
    app.include_router(decision_record_router)

    async def _user():
        return {"sub": "u1", "role": "analyst", "ws_id": "ws-a"}

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_current_workspace] = lambda: "ws-a"
    monkeypatch.setattr(
        "odap.biz.decision.decision_record.api.routes.get_decision_service", lambda: service
    )
    return TestClient(app)


# ---------------- 非法迁移：409 + code ----------------


def test_illegal_transition_raises_conflict_error():
    with pytest.raises(ConflictError) as exc:
        assert_transition("pending", "executed")
    assert exc.value.status_code == 409
    assert exc.value.error_code == "illegal_transition"
    assert exc.value.details["current_status"] == "pending"


def test_illegal_transition_is_api_error_so_middleware_keeps_409():
    # 若继承 ValueError，中间件会把它压成 400，前端读不到 code
    assert issubclass(ConflictError, APIError)
    assert not issubclass(ConflictError, ValueError)


def test_legal_transition_passes():
    assert_transition("pending", "decided")
    assert_transition("decided", "executing")
    assert_transition("executing", "executed")


def test_unknown_status_still_conflicts():
    with pytest.raises(ConflictError):
        assert_transition("weird", "decided")


# ---------------- 单一 patch 写侧 ----------------


def test_outcome_update_requires_status():
    """载荷缺 status 必须 422：没有 status 就无法校验矩阵，等于散写。"""
    assert StatusOutcomePatch.model_fields["status"].is_required()
    assert OutcomeUpdate.model_fields["status"].is_required()


def test_endpoint_writes_single_patch(client, store):
    resp = client.patch(
        "/api/decisions/dec_1/outcome",
        json={
            "status": "executed",
            "outcome": "success",
            "outcome_details": {"action_status": "completed"},
        },
    )
    assert resp.status_code == 200, resp.text
    _, workspace_id, patch, _ = store.patches[0]
    node_patch = patch.to_node_patch()
    assert workspace_id == "ws-a"
    assert node_patch["status"] == "executed"
    assert node_patch["outcome"] == "success"
    # details 与状态同一份 patch，且进 outcome_details（读侧只认这个属性）
    assert json.loads(node_patch["outcome_details"])["action_status"] == "completed"
    assert "updated_at" in node_patch


def test_endpoint_missing_status_is_422(client):
    resp = client.patch("/api/decisions/dec_1/outcome", json={"outcome": "success"})
    assert resp.status_code == 422


def test_endpoint_rejects_illegal_combination(client, store):
    """`pending + success` 非法：抛内部不变量错误，不得被压成 422 字符串。"""
    with pytest.raises(DecisionInvariantError):
        client.patch(
            "/api/decisions/dec_1/outcome",
            json={"status": "pending", "outcome": "success"},
        )
    assert store.patches == []


def test_service_update_takes_patch_not_loose_fields():
    from odap.biz.decision.decision_record.services.decision_service import DecisionService

    params = inspect.signature(DecisionService.update_decision_outcome).parameters
    assert "patch" in params
    assert "outcome" not in params
    assert "outcome_details" not in params


def test_store_update_takes_patch_not_loose_fields():
    params = inspect.signature(Neo4jDecisionStore.update_outcome).parameters
    assert "patch" in params
    assert "outcome" not in params


@pytest.mark.asyncio
async def test_store_cypher_writes_patch_in_one_statement(monkeypatch):
    """反例断言：改了签名但 Cypher 仍逐字段 SET，则本条红。"""
    captured = {}

    class _Driver:
        async def execute_query(self, cypher, **kwargs):
            captured["cypher"] = cypher
            captured["kwargs"] = kwargs
            return [{"uuid": "dec_1"}], None, None

    monkeypatch.setattr(
        "odap.biz.decision.decision_record.impl.neo4j_decision_store.get_decision_driver",
        lambda: _Driver(),
    )
    patch = StatusOutcomePatch(
        status="executed", outcome=DecisionOutcome.SUCCESS,
        details={"action_status": "completed"},
    )
    ok = await Neo4jDecisionStore().update_outcome("dec_1", "ws-a", patch, "已完成")

    assert ok is True
    assert "SET n += $patch" in captured["cypher"]
    assert "n.outcome =" not in captured["cypher"]  # 逐字段散写已消除
    assert captured["kwargs"]["patch"]["status"] == "executed"
