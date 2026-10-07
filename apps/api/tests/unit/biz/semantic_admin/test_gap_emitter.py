import logging
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
from odap.biz.semantic_admin.gap_pool.services import GapService
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


def test_service_record_signal_ok(store):
    svc = GapService(storage=store)
    r = svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力",
                          workspace_id="ws1", domain_id="d1")
    assert r["status"] == "ok"
    assert r["gap"]["heat"] == 1


def test_service_record_signal_empty_expression_is_error(store):
    svc = GapService(storage=store)
    r = svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "   ")
    assert r["status"] == "error"


def test_emitter_records_through_module_singleton(store, monkeypatch):
    monkeypatch.setattr(gap_emitter, "_get_service", lambda: GapService(storage=store))
    before = gap_emitter.get_emit_failures()
    gap_emitter.report_gap_signal(GapSignalSource.QA_UNANSWERED, "诸侯",
                                  workspace_id="ws1")
    assert gap_emitter.get_emit_failures() == before
    assert store.get_by_expression("诸侯", "ws1::-") is not None


def test_emitter_swallows_exception_and_counts(store, monkeypatch, caplog):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(gap_emitter, "_get_service", boom)
    before = gap_emitter.get_emit_failures()
    with caplog.at_level(logging.WARNING):
        gap_emitter.report_gap_signal(GapSignalSource.QA_UNANSWERED, "x")  # 不 raise
    assert gap_emitter.get_emit_failures() == before + 1
    assert any("缺口信号" in r.message or "gap" in r.message.lower()
               for r in caplog.records)


def test_stats_shape(store):
    svc = GapService(storage=store)
    svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "势力", workspace_id="ws1")
    s = svc.stats()
    assert s["status"] == "ok"
    assert s["total"] == 1
    assert s["by_status"]["open"] == 1
    assert s["adoption_rate"] is None          # 分母 0 不造数
    assert "emit_failures" in s
