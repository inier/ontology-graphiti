"""子项目 B：配对回放 runner 测试（真实函数体，规则 14.6）。

覆盖：
- 判定逻辑：fixed / regressed / unchanged / verdict（pass ⇔ 回归 0 且修复≥1）
- 生产语义：before = 捕获证据（缺口即未答），after = 现场回放
- 信号收集器：回放期间 report_gap_signal 被替换为内存收集器，
  绝不写 concept_gaps（E-f：SQL 断言 heat 不变、池零写入）
- 收集器异常 → verdict=error 且 error_detail 非空具体（规则 14）
"""
import asyncio
import sqlite3

import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.gap_pool.regression.runner import PairedReplayRunner

_CASES = [{"query": "诸侯是谁", "expression": "诸侯", "gap_id": "g1",
           "source": "term_resolve_miss"}]


class _FakePipeline:
    """边界依赖桩（同 test_gap_wiring 的 RAG 桩范式）：query() 内部走真实
    gap_emitter 发射路径（qa_unanswered），由 runner 的收集器接管——验证
    收集器/恢复逻辑为真实函数体。answered_by_query 控制哪些 query 未答。
    """

    def __init__(self, unanswered_queries):
        self.unanswered = set(unanswered_queries)
        self.calls = []

    async def query(self, request):
        self.calls.append(request.query)
        if request.query in self.unanswered:
            # 走真实接线语义：未答 → 发 QA_UNANSWERED（此刻被收集器截获）
            gap_emitter.report_gap_signal(GapSignalSource.QA_UNANSWERED,
                                          request.query, ref="gap-replay-test")
        from odap.biz.data.qa.models import QueryResponse
        return QueryResponse(answer="ok")


@pytest.fixture
def gap_store(tmp_path, monkeypatch):
    """真实缺口库 + emitter 单例指向它——回放结束后可断言零写入。"""
    store = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    svc = GapService(storage=store)
    monkeypatch.setattr(gap_emitter, "_service_singleton", svc)
    return store


def _run(coro):
    return asyncio.run(coro)


def test_evidence_before_plus_live_after_verdict_pass(gap_store):
    """生产主场景：before=捕获证据（未答）→ after 现场已修复 → fixed≥1, pass。"""
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            domain_id="d1")   # 捕获证据存在（回放不得动它）
    pipeline = _FakePipeline(unanswered_queries=[])   # after：全部答上
    runner = PairedReplayRunner(pipeline=pipeline)
    r = _run(runner.replay(_CASES, workspace_id="ws1"))
    assert r["verdict"] == "pass"
    assert r["fixed_count"] == 1
    assert r["regressed_count"] == 0
    assert r["unchanged_count"] == 0
    assert r["rounds"][0] == {"query": "诸侯是谁",
                              "before_answered": False, "after_answered": True}
    assert r["cost"]["before_mode"] == "captured_evidence"
    assert r["cost"]["after_ms"] >= 0
    assert r["error_detail"] is None


def test_still_unanswered_verdict_fail(gap_store):
    pipeline = _FakePipeline(unanswered_queries=["诸侯是谁"])
    runner = PairedReplayRunner(pipeline=pipeline)
    r = _run(runner.replay(_CASES, workspace_id="ws1"))
    assert r["verdict"] == "fail"          # fixed=0（且无回归）→ 不达 pass
    assert r["fixed_count"] == 0
    assert r["unchanged_count"] == 1


def test_regressed_case_blocks_pass(gap_store):
    """注入 before 执行器（现场双轮配对）：before 答上 / after 答不上 → regressed。"""
    pipeline = _FakePipeline(unanswered_queries=["诸侯是谁"])

    async def before_answered(case):
        return True

    runner = PairedReplayRunner(pipeline=pipeline)
    r = _run(runner.replay(_CASES, workspace_id="ws1",
                           before_executor=before_answered))
    assert r["regressed_count"] == 1
    assert r["fixed_count"] == 0
    assert r["verdict"] == "fail"          # 回归红线：regressed>0 绝不 pass


def test_replay_never_writes_concept_gaps(gap_store):
    """E-f / M1 纪律：回放期间收集器截获信号，concept_gaps 零写入。"""
    g = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                domain_id="d1")
    heat_before = gap_store.get_gap(g["id"])["heat"]
    pipeline = _FakePipeline(unanswered_queries=["诸侯是谁"])  # 未答信号高频触发
    runner = PairedReplayRunner(pipeline=pipeline)
    r = _run(runner.replay(_CASES + _CASES, workspace_id="ws1"))
    assert r["verdict"] == "fail"
    # SQL 断言：池内仍只有捕获时的 1 条，heat 不变
    conn = sqlite3.connect(gap_store.db_path)
    n = conn.execute("SELECT COUNT(*) FROM concept_gaps").fetchone()[0]
    conn.close()
    assert n == 1
    assert gap_store.get_gap(g["id"])["heat"] == heat_before


def test_collector_restored_after_replay(gap_store):
    """回放结束恢复原 emitter 函数（D6）：此后信号正常落库。"""
    real = gap_emitter.report_gap_signal
    pipeline = _FakePipeline(unanswered_queries=[])
    runner = PairedReplayRunner(pipeline=pipeline)
    _run(runner.replay(_CASES, workspace_id="ws1"))
    assert gap_emitter.report_gap_signal is real
    # 恢复后正常落库（对照：守卫没把运行时归因路径永久关掉）
    gap_emitter.report_gap_signal(GapSignalSource.TERM_RESOLVE_MISS, "阵营",
                                  domain_id="d1")
    assert gap_store.get_by_expression("阵营", "-::d1") is not None


def test_executor_error_verdict_error_with_detail(gap_store):
    """规则 14：失败显式——执行器异常 → verdict=error + 具体原因。"""

    class _BoomPipeline:
        async def query(self, request):
            raise RuntimeError("Neo4j connection refused (bolt://localhost:7687)")

    runner = PairedReplayRunner(pipeline=_BoomPipeline())
    r = _run(runner.replay(_CASES, workspace_id="ws1"))
    assert r["verdict"] == "error"
    assert r["error_detail"] and "Neo4j" in r["error_detail"]
    assert r["fixed_count"] == 0 and r["regressed_count"] == 0
    # error 后 emitter 已恢复（finally 纪律）
    assert gap_emitter.report_gap_signal is not None


def test_model_fingerprint_recorded(gap_store):
    pipeline = _FakePipeline(unanswered_queries=[])
    runner = PairedReplayRunner(pipeline=pipeline)
    r = _run(runner.replay(_CASES, workspace_id="ws1"))
    assert r["model_id"]                       # 指纹非空（backbone-conditional）
    assert "prompt_version" in r
