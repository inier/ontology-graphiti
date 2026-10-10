"""端到端验收（子项目 D E-14/E-15）：三路 promote 分流 + 门控（不自动改 schema）。

用一个 GapService 实例，三条不同 layer 的缺口分别 promote，验证各自落到
候选 / 结构提案 / 工单，且结构提案始终为 draft（人工门控）。
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
from odap.biz.semantic_admin.routing_tickets.services.ticket_service import (
    TicketService,
)
from odap.biz.semantic_admin.routing_tickets.storage import SQLiteTicketStorage


@pytest.fixture
def svc_and_stores(tmp_path):
    gstore = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    cstore = SQLiteCandidateStorage(db_path=str(tmp_path / "cand.db"))
    pstore = SQLiteGoalStorage(db_path=str(tmp_path / "goal.db"))
    tstore = SQLiteTicketStorage(db_path=str(tmp_path / "tickets.db"))
    svc = GapService(storage=gstore)
    svc._candidate_service_factory = lambda: CandidateService(storage=cstore)
    svc._goal_storage_factory = lambda: pstore
    svc._ticket_service_factory = lambda: TicketService(storage=tstore)
    return svc, gstore, cstore, pstore, tstore


def _gap(gstore, source, expr, attribution):
    return gstore.record_signal(source, expr, workspace_id="ws1", domain_id="d1",
                                attribution=attribution)


def test_three_layer_promote_end_to_end(svc_and_stores):
    svc, gstore, cstore, pstore, tstore = svc_and_stores

    g_content = _gap(gstore, GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                     {"layer": GapLayer.CONTENT.value, "target_kind": "term"})
    g_schema = _gap(gstore, GapSignalSource.MAPPING_FAILURE, "司马懿",
                    {"layer": GapLayer.SCHEMA.value, "target_kind": "object_type"})
    g_tool = _gap(gstore, GapSignalSource.NL_QUERY_UNANSWERED, "找相似武将",
                  {"layer": GapLayer.TOOL.value, "target_ref": "nl_engine"})

    rc = svc.promote(g_content["id"], actor="alice")
    rs = svc.promote(g_schema["id"], actor="alice")
    rt = svc.promote(g_tool["id"], actor="alice")

    # 路由正确
    assert (rc["routed_to"], rs["routed_to"], rt["routed_to"]) == (
        "candidate_store", "change_proposal", "tool_routing")

    # content → 候选（下游侧道推进 gap 状态）
    assert cstore.get_candidate(rc["candidate_id"]) is not None
    # schema → 结构提案（draft 门控，E-15）
    prop = pstore.get_proposal(rs["proposal_id"])
    assert prop is not None and prop["status"] == "draft"
    assert prop["changes"][0]["path"] == "/object_types/司马懿"
    # tool → 工单
    assert tstore.get_ticket(rt["ticket_id"])["status"] == "open"

    # 三个 gap 均 promoted，且各自回填指向自己那路产物
    assert gstore.get_gap(g_content["id"])["promoted_candidate_id"] == rc["candidate_id"]
    assert gstore.get_gap(g_schema["id"])["promoted_proposal_id"] == rs["proposal_id"]
    assert gstore.get_gap(g_tool["id"])["promoted_ticket_id"] == rt["ticket_id"]
    for g in (g_content, g_schema, g_tool):
        assert gstore.get_gap(g["id"])["status"] == GapStatus.PROMOTED.value


def test_schema_proposal_not_auto_implemented(svc_and_stores):
    """E-15：schema promote 只建 draft 提案，绝不改本体（门控归人，D-D7）。"""
    svc, gstore, _c, pstore, _t = svc_and_stores
    g = _gap(gstore, GapSignalSource.MAPPING_FAILURE, "结义",
             {"layer": GapLayer.SCHEMA.value, "target_kind": "relation_type"})

    r = svc.promote(g["id"], actor="alice")

    prop = pstore.get_proposal(r["proposal_id"])
    assert prop["status"] == "draft"            # 未审批
    assert prop["impact_analysis_id"] is None   # 未跑 Impact（D-D4）
    assert prop["reviewed_at"] is None
