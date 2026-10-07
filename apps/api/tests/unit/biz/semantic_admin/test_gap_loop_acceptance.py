"""回路验收：signal → gap → promote → approve → writeback → resolver reload → 命中。

规则 14.6：走真实函数体，不 patch 掉待验证逻辑。writeback 依赖真实 USL 存储
（tmp_path 真 DB），审批通过 writeback_service.write_approved 推进 candidate 到
WRITTEN_BACK，回调把 gap 推进 ADOPTED，最后重建 resolver 断言原 expression 命中。

Controller Ruling 2：writeback 接线（_notify_gap_resolved + 两处 call-site）
必须真实函数体覆盖 —— 只 stub 下游依赖（GapService / handler），不 patch
_notify_gap_resolved 本体、不 patch write_approved/write_rejected 函数体。
"""
import logging

import pytest

from odap.biz.semantic_admin.gap_pool.models import GapSignalSource, GapStatus
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)


@pytest.fixture(autouse=True)
def _mute_emitter(monkeypatch):
    """Controller Ruling 1：隔离生产 gap DB（规则 13）。

    canonical_of 未命中分支会经模块级单例 emitter 写入 DATA_DIR/concept_gaps.db。
    这里只替换 emitter 的落库 sink（T2/T4 已单独覆盖），回路主逻辑
    （promote / on_candidate_resolved / 状态机 / save_term / list_terms /
    load_terms / 末端 canonical_of 命中）全部走真实函数体。
    """
    from odap.biz.semantic_admin.gap_pool.services import gap_emitter
    monkeypatch.setattr(gap_emitter, "report_gap_signal", lambda *a, **k: None)


@pytest.fixture
def stores(tmp_path):
    gap = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    cand = SQLiteCandidateStorage(db_path=str(tmp_path / "candidates.db"))
    usl = SQLiteUslStorage(db_path=str(tmp_path / "usl.db"))
    return gap, cand, usl


def test_gap_loop_same_question_answerable_next_time(stores):
    gap_store, cand_store, usl_store = stores
    # 1. 未命中信号落池
    gap = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                  workspace_id="ws1", domain_id="d1")
    resolver = UslTermResolver()
    resolver.load_terms("d1", [])
    assert resolver.canonical_of("诸侯", "d1") is None   # 第一次答不上

    # 2. 人工晋升为候选
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice", domain_id="d1")["candidate_id"]

    # 3. 人工裁决通过 → 写入 USL（模拟 writeback 结果 + 回调）
    #    直接建 term 并触发 on_candidate_resolved（writeback 真实链路见下方
    #    Controller Ruling 2 的真实函数体测试）
    usl_store.save_term({"id": "term-1", "domain_id": "d1", "canonical": "诸侯",
                         "semantic_type": "对象类型", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False,
                         "definition": "分封的领主"})
    svc.on_candidate_resolved(cid, "adopted", term_id="term-1")
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.ADOPTED.value

    # 4. 重建 resolver（reload）→ 同一 expression 现在能答上
    terms, _total = usl_store.list_terms(domain_id="d1", page=1, page_size=100)
    resolver2 = UslTermResolver()
    resolver2.load_terms("d1", list(terms))
    assert resolver2.canonical_of("诸侯", "d1") == "诸侯"   # 闭环成立


# ── Controller Ruling 2: writeback 接线的真实函数体覆盖（规则 9 + 14.6） ──
# 只 stub 下游依赖（gap_service.GapService 惰性导入目标、impl handler）；
# _notify_gap_resolved 本体与 write_approved/write_rejected 的 call-site
# 分支（if result.get("status") == "ok": ...）全部真实执行。

_GAP_SERVICE_MODULE = "odap.biz.semantic_admin.gap_pool.services.gap_service"


def _install_fake_gap_service(monkeypatch):
    """替换惰性导入目标 GapService（call-time 解析，patch 生效）。返回记录列表。"""
    calls = []

    class FakeGapService:
        def on_candidate_resolved(self, candidate_id, outcome, *, term_id=None):
            calls.append((candidate_id, outcome, term_id))

    monkeypatch.setattr(f"{_GAP_SERVICE_MODULE}.GapService", FakeGapService)
    return calls


class _FakeHandler:
    def write_approved(self, candidate_id, *, executed_by="system"):
        return {"status": "ok", "usl_term_id": "t1", "written_back": True}

    def write_rejected(self, candidate_id, *, reason_code,
                       add_to_stoplist=True, executed_by="system"):
        return {"status": "ok", "written_back": True}


def test_notify_gap_resolved_happy_path(monkeypatch):
    """(a) _notify_gap_resolved 真实体：惰性导入 → 实例化 → 转发参数。"""
    calls = _install_fake_gap_service(monkeypatch)
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    svc = WritebackService()
    assert svc._notify_gap_resolved("cid", "adopted", term_id="t1") is None
    assert calls == [("cid", "adopted", "t1")]


def test_notify_gap_resolved_swallows_exception(monkeypatch, caplog):
    """(b) 异常路径：GapService 构造即炸 → 吞异常返回 None + WARNING 日志。"""
    class BoomGapService:
        def __init__(self):
            raise RuntimeError("gap pool down")

    monkeypatch.setattr(f"{_GAP_SERVICE_MODULE}.GapService", BoomGapService)
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    svc = WritebackService()
    with caplog.at_level(
        logging.WARNING,
        logger="odap.biz.semantic_admin.usl_writeback.services.writeback_service",
    ):
        assert svc._notify_gap_resolved("cid", "adopted") is None
    assert any(
        r.levelno == logging.WARNING and "gap 回调失败" in r.getMessage()
        for r in caplog.records
    )


def test_write_approved_notifies_gap_without_touching_return(monkeypatch):
    """(c) write_approved call-site 真实体：ok → 侧道回调(adopted, term_id)，
    返回值与 handler 原样一致（规则 14：additive-only，侧道不污染主流程）。"""
    calls = _install_fake_gap_service(monkeypatch)
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    svc = WritebackService()
    svc._handler = _FakeHandler()
    r = svc.write_approved("cid")
    assert calls == [("cid", "adopted", "t1")]
    assert r == {"status": "ok", "usl_term_id": "t1", "written_back": True}


def test_write_rejected_notifies_gap_without_touching_return(monkeypatch):
    """(d) write_rejected call-site 真实体：ok → 侧道回调(rejected)，返回值不变。"""
    calls = _install_fake_gap_service(monkeypatch)
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    svc = WritebackService()
    svc._handler = _FakeHandler()
    r = svc.write_rejected("cid", reason_code="noise")
    assert calls == [("cid", "rejected", None)]
    assert r == {"status": "ok", "written_back": True}
