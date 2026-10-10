"""TDD：promote schema 路径（子项目 D E-3/E-4/E-15）。

schema 层缺口 promote → 构造 ChangeProposal（RFC 6902）落 change_proposals 表，
gap 状态 promoted + promoted_proposal_id 回填；提案 status=draft，不自动实施。
"""
import pytest

from odap.biz.core.ontology.goal.storage import SQLiteGoalStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.gap_pool.models import (
    GapLayer,
    GapSignalSource,
    GapStatus,
)
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def gap_store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


@pytest.fixture
def goal_store(tmp_path):
    return SQLiteGoalStorage(db_path=str(tmp_path / "goal.db"))


def _schema_gap(gap_store, expr="司马懿", kind="object_type", **extra):
    return gap_store.record_signal(
        GapSignalSource.MAPPING_FAILURE, expr,
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": GapLayer.SCHEMA.value, "target_kind": kind, **extra},
    )


def _svc(gap_store, goal_store):
    svc = GapService(storage=gap_store)
    svc._goal_storage_factory = lambda: goal_store
    return svc


def test_schema_promote_creates_draft_proposal(gap_store, goal_store):
    gap = _schema_gap(gap_store)
    svc = _svc(gap_store, goal_store)

    r = svc.promote(gap["id"], actor="alice")

    assert r["status"] == "ok"
    assert r["layer"] == "schema"
    assert r["routed_to"] == "change_proposal"
    pid = r["proposal_id"]
    assert pid

    # gap 回填 + promoted
    g2 = gap_store.get_gap(gap["id"])
    assert g2["status"] == GapStatus.PROMOTED.value
    assert g2["promoted_proposal_id"] == pid

    # proposal 落库，changes 是 RFC 6902；E-15：status=draft 不自动实施
    prop = goal_store.get_proposal(pid)
    assert prop is not None
    assert prop["status"] == "draft"
    assert prop["changes"] == [
        {"op": "add", "path": "/object_types/司马懿", "value": {"name": "司马懿"}}
    ]
    assert prop["goal_id"] == f"gap:{gap['id']}"
    assert prop["proposed_by"] == "alice"


def test_schema_promote_property_uses_parent(gap_store, goal_store):
    gap = _schema_gap(gap_store, expr="寿命", kind="property", parent="人物")
    svc = _svc(gap_store, goal_store)

    r = svc.promote(gap["id"], actor="alice")

    prop = goal_store.get_proposal(r["proposal_id"])
    assert prop["changes"][0]["path"] == "/object_types/人物/properties/寿命"


def test_schema_promote_relation_type(gap_store, goal_store):
    gap = _schema_gap(gap_store, expr="结义", kind="relation_type")
    svc = _svc(gap_store, goal_store)

    r = svc.promote(gap["id"], actor="alice")

    prop = goal_store.get_proposal(r["proposal_id"])
    assert prop["changes"][0]["path"] == "/relation_types/结义"


def test_schema_promote_empty_patch_is_explicit_error(gap_store, goal_store):
    """E-4：无法推导结构变更 → 显式失败，不造空壳提案（规则 14 不造数）。"""
    gap = _schema_gap(gap_store, expr="怪东西", kind="unknown_kind")
    svc = _svc(gap_store, goal_store)

    r = svc.promote(gap["id"], actor="alice")

    assert r["status"] == "error"
    assert r["code"] == "SCHEMA_PATCH_EMPTY"
    assert goal_store.list_proposals() == []
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.OPEN.value


def test_force_layer_content_overrides_schema(gap_store, goal_store, tmp_path):
    """D-D1：force_layer 覆盖自动判定——schema 缺口强制走 content 路径。"""
    cand_store = SQLiteCandidateStorage(db_path=str(tmp_path / "cand.db"))
    gap = _schema_gap(gap_store)
    svc = _svc(gap_store, goal_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)

    r = svc.promote(gap["id"], actor="alice", force_layer="content")

    assert r["status"] == "ok"
    assert r["routed_to"] == "candidate_store"
    assert r["candidate_id"]
    assert goal_store.list_proposals() == []
    assert gap_store.get_gap(gap["id"])["promoted_candidate_id"] == r["candidate_id"]


def test_schema_promote_is_idempotent(gap_store, goal_store):
    gap = _schema_gap(gap_store)
    svc = _svc(gap_store, goal_store)

    first = svc.promote(gap["id"], actor="alice")
    second = svc.promote(gap["id"], actor="alice")

    assert second.get("already_promoted") is True
    assert second["proposal_id"] == first["proposal_id"]
    assert len(goal_store.list_proposals()) == 1
