import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource, GapStatus
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.candidate_store.services import CandidateService


@pytest.fixture
def gap_store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


@pytest.fixture
def cand_store(tmp_path):
    return SQLiteCandidateStorage(db_path=str(tmp_path / "candidates.db"))


def _seed_gap(gap_store, expr="势力", ws="ws1", dom="d1"):
    return gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                                   workspace_id=ws, domain_id=dom)


def test_promote_creates_run_and_candidate(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    r = svc.promote(gap["id"], actor="alice")
    assert r["status"] == "ok"
    cand = cand_store.get_candidate(r["candidate_id"])
    assert cand is not None
    assert cand["canonical"] == "势力"
    assert cand["source_text"] == "势力"
    prov = cand["provenance_json"]
    assert prov["source_type"] == "concept_gap"
    assert prov["gap_id"] == gap["id"]
    # gap 转 PROMOTED
    g2 = gap_store.get_gap(gap["id"])
    assert g2["status"] == GapStatus.PROMOTED.value
    assert g2["promoted_candidate_id"] == r["candidate_id"]


def test_promote_missing_gap_is_error(gap_store, cand_store):
    svc = GapService(storage=gap_store)
    r = svc.promote("nope", actor="alice")
    assert r["status"] == "error"


def test_on_candidate_resolved_adopted(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice")["candidate_id"]
    svc.on_candidate_resolved(cid, "adopted", term_id="term-99")
    g = gap_store.get_gap(gap["id"])
    assert g["status"] == GapStatus.ADOPTED.value
    assert g["resolved_term_id"] == "term-99"


def test_on_candidate_resolved_rejected(gap_store, cand_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    svc._candidate_service_factory = lambda: CandidateService(storage=cand_store)
    cid = svc.promote(gap["id"], actor="alice")["candidate_id"]
    svc.on_candidate_resolved(cid, "rejected")
    assert gap_store.get_gap(gap["id"])["status"] == GapStatus.REJECTED.value


def test_on_candidate_resolved_unknown_is_noop(gap_store):
    svc = GapService(storage=gap_store)
    svc.on_candidate_resolved("no-such-cand", "adopted")  # 不抛


def test_dismiss_writes_reason(gap_store):
    gap = _seed_gap(gap_store)
    svc = GapService(storage=gap_store)
    r = svc.dismiss(gap["id"], reason="噪声", actor="bob")
    assert r["status"] == "ok"
    g = gap_store.get_gap(gap["id"])
    assert g["status"] == GapStatus.REJECTED.value
    assert g["dismiss_reason"] == "噪声"


def test_resolve_check_is_read_only_no_signal(gap_store, monkeypatch):
    """终审 M1 回归：resolve-check 是只读判定，绝不发缺口信号。

    修前：resolve_check → canonical_of 未命中 → 发 TERM_RESOLVE_MISS（经 emitter
    全局单例落库）→ record_signal 命中同 scope_key 行 → heat+1 且把已 dismiss 的
    缺口 REJECTED→OPEN 复活，静默推翻人工裁决。
    修后：canonical_of(emit=False) → 不发任何信号 → 无任何 heat/状态副作用。

    canonical_of 走真实函数体（规则 14.6）；只把 emitter sink 换成内存收集器，
    并注入 load_resolver_from_storage 返回空的真 resolver（无术语→必 miss）。
    核心断言用「收集器为空」而非「tmp_path 行不变」——因为 buggy 再发射经全局单例
    落的是另一个 DB，只有信号层断言才真正锁住 M1。
    """
    from odap.biz.semantic_admin.gap_pool.services import gap_emitter
    from odap.biz.semantic_admin.usl_manager.services import usl_term_resolver as utr

    emitted = []
    monkeypatch.setattr(gap_emitter, "report_gap_signal",
                        lambda *a, **k: emitted.append((a, k)))
    monkeypatch.setattr(utr, "load_resolver_from_storage",
                        lambda dom, storage=None: utr.UslTermResolver())

    # 按运行时 term_resolve_miss 的真实 scope 播种：canonical_of 发信号只带 domain_id、
    # 不带 workspace_id → scope_key "-::d1"，与 resolve-check 潜在再发射同键。
    gap = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                  domain_id="d1")
    svc = GapService(storage=gap_store)
    svc.dismiss(gap["id"], reason="噪声", actor="bob")
    before = gap_store.get_gap(gap["id"])
    assert before["status"] == GapStatus.REJECTED.value

    r = svc.resolve_check(gap["id"])
    assert r["status"] == "ok"
    assert r["resolvable"] is False

    # M1 核心断言：resolve-check 未发任何信号
    assert emitted == []
    # 缺口行原样：未复活、heat 未变、裁决记录完好
    after = gap_store.get_gap(gap["id"])
    assert after["status"] == GapStatus.REJECTED.value
    assert after["heat"] == before["heat"]
    assert after["dismiss_reason"] == "噪声"
