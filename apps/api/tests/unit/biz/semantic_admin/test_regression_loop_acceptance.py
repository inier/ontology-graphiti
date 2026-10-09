"""子项目 B：回路验收升级（E-i）——

signal → gap(带 attribution) → build set → promote → approve → writeback →
replay → verdict=pass ∧ fixed≥1。

把 BeModel"同一个问题下次能答上"从 promote 单点判定（test_gap_loop_acceptance）
升级为问答语义上的回放判定。规则 14.6：runner 判定/差分/verdict、builder 固化、
真实 resolver 归一全部走真实函数体；仅 pipeline 为边界桩（桩内调用**真实**
UslTermResolver.canonical_of(emit=False) 决定 answered，与生产管线经理解层
归一的真实语义一致——生产管线本身由 benchmark/qa 测试覆盖）。
"""
import asyncio

import pytest

from odap.biz.semantic_admin.gap_pool.models import GapSignalSource, GapStatus
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.gap_pool.regression.builder import RegressionSetBuilder
from odap.biz.semantic_admin.gap_pool.regression.runner import PairedReplayRunner
from odap.biz.semantic_admin.gap_pool.regression.service import RegressionService
from odap.biz.semantic_admin.gap_pool.regression.storage import SQLiteGapRegressionStorage
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import UslTermResolver


class _ResolverBackedPipeline:
    """边界桩：answered = 真实 resolver.canonical_of(emit=False) 命中。"""

    def __init__(self, resolver: UslTermResolver, domain_id: str):
        self._resolver = resolver
        self._domain = domain_id

    async def query(self, request):
        from odap.biz.data.qa.models import QueryResponse
        expr = request.query
        # 走真实归一函数体；emit=False 守读侧纪律（回放绝不写缺口池）
        canonical = self._resolver.canonical_of(expr, self._domain, emit=False)
        if canonical is None:
            gap_emitter.report_gap_signal(
                GapSignalSource.QA_UNANSWERED, expr,
                domain_id=self._domain, ref="gap-replay-acceptance")
        return QueryResponse(answer="ok" if canonical else "未找到相关信息")


@pytest.fixture(autouse=True)
def _isolate_emitter(monkeypatch, tmp_path):
    """emitter 单例指向 tmp 缺口库：回放守卫断言（零写入）可在同库 SQL 验证。"""
    store = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    svc = GapService(storage=store)
    monkeypatch.setattr(gap_emitter, "_service_singleton", svc)
    return store


def test_full_loop_replay_passes_after_writeback(tmp_path, _isolate_emitter):
    gap_store = _isolate_emitter
    cand_store = SQLiteCandidateStorage(db_path=str(tmp_path / "candidates.db"))
    usl_store = SQLiteUslStorage(db_path=str(tmp_path / "usl.db"))
    reg_store = SQLiteGapRegressionStorage(db_path=str(tmp_path / "gap_regression.db"))

    # 1. 未命中信号落池（带 content 归因）
    gap = gap_store.record_signal(
        GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": "content", "target_kind": "对象类型",
                     "target_ref": "诸侯"})
    resolver = UslTermResolver()
    resolver.load_terms("d1", [])
    assert resolver.canonical_of("诸侯", "d1") is None       # 第一次答不上

    # 2. 固化回归集（before = 捕获证据：未答）
    builder = RegressionSetBuilder(gap_storage=gap_store, storage=reg_store)
    built = builder.build(workspace_id="ws1", domain_id="d1")
    assert built["set"]["case_count"] == 1

    # 3. 人工晋升 → 人工裁决采纳 → 写回 USL（真实存储）
    gap_svc = GapService(storage=gap_store)
    gap_svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = gap_svc.promote(gap["id"], actor="alice", domain_id="d1")["candidate_id"]
    usl_store.save_term({"id": "term-1", "domain_id": "d1", "canonical": "诸侯",
                         "semantic_type": "对象类型", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False,
                         "definition": "分封的领主"})
    gap_svc.on_candidate_resolved(cid, "adopted", term_id="term-1")
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.ADOPTED.value

    # 4. 重建 resolver（reload）→ 回放：同一个问题现在能答上
    terms, _total = usl_store.list_terms(domain_id="d1", page=1, page_size=100)
    resolver2 = UslTermResolver()
    resolver2.load_terms("d1", list(terms))

    reg_svc = RegressionService(
        storage=reg_store,
        runner=PairedReplayRunner(
            pipeline=_ResolverBackedPipeline(resolver2, "d1")),
    )
    r = asyncio.run(reg_svc.replay(built["set_id"]))
    assert r["status"] == "ok"
    report = r["report"]
    assert report["verdict"] == "pass"                     # E-i 验收口径
    assert report["fixed_count"] >= 1
    assert report["regressed_count"] == 0
    assert report["rounds_json"][0]["before_answered"] is False
    assert report["rounds_json"][0]["after_answered"] is True
    # 报告不可变落库，详情可查
    persisted = reg_store.get_report(report["id"])
    assert persisted["verdict"] == "pass"
    # 回放零写入缺口池（heat 仍为捕获时的 1）
    assert gap_store.get_gap(gap["id"])["heat"] == 1


# ── writeback 侧道自动回放（ADR-088 D8：默认 off，异常绝不传播主路径） ──────

def test_auto_replay_side_channel_default_off(monkeypatch):
    """默认 off：_maybe_auto_replay 立即返回，不触碰任何回归设施。"""
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    monkeypatch.delenv("GAP_REGRESSION_AUTO_REPLAY", raising=False)
    svc = WritebackService()
    # 默认 off 下不应触发 RegressionService 构造（其导入若被触发会走真实
    # 构造写 DATA_DIR）；函数正常返回即证明开关短路生效
    assert svc._maybe_auto_replay("cid-1") is None


def test_auto_replay_side_channel_no_event_loop_warns(monkeypatch, caplog):
    """开关 on 但无事件循环：显式 warning（规则 14），不 raise。"""
    import logging as _logging
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    monkeypatch.setenv("GAP_REGRESSION_AUTO_REPLAY", "on")
    svc = WritebackService()
    with caplog.at_level(
        _logging.WARNING,
        logger="odap.biz.semantic_admin.usl_writeback.services.writeback_service",
    ):
        assert svc._maybe_auto_replay("cid-1") is None
    assert any("无事件循环" in r.getMessage() for r in caplog.records)


def test_auto_replay_side_channel_creates_task(monkeypatch):
    """开关 on + 有事件循环：create_task 触发 scope 回放；内部异常只 warning。"""
    import asyncio
    from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
        WritebackService,
    )
    monkeypatch.setenv("GAP_REGRESSION_AUTO_REPLAY", "on")

    calls = {}

    class _FakeGapSvc:
        class storage:
            @staticmethod
            def get_by_candidate_id(cid):
                calls["candidate"] = cid
                return {"id": "g1", "scope_key": "ws1::d1"}

    class _FakeRegSvc:
        async def auto_replay_for_scope(self, scope_key):
            calls["scope"] = scope_key
            return {"status": "ok"}

    import odap.biz.semantic_admin.gap_pool.services.gap_service as gs_mod
    import odap.biz.semantic_admin.gap_pool.regression.service as rs_mod
    monkeypatch.setattr(gs_mod, "GapService", _FakeGapSvc)
    monkeypatch.setattr(rs_mod, "RegressionService", _FakeRegSvc)

    async def main():
        svc = WritebackService()
        assert svc._maybe_auto_replay("cid-9") is None
        # 让 create_task 的协程有机会执行
        await asyncio.sleep(0)

    asyncio.run(main())
    assert calls["candidate"] == "cid-9"
    assert calls["scope"] == "ws1::d1"
