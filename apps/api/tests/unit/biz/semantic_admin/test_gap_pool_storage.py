import pytest
from odap.biz.semantic_admin.gap_pool.models import (
    GapStatus, GapSignalSource, make_scope_key,
)
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


def test_scope_key_handles_none():
    assert make_scope_key(None, None) == "-::-"
    assert make_scope_key("ws1", "d1") == "ws1::d1"


def test_record_signal_creates_then_increments_heat(store):
    g1 = store.record_signal(
        source=GapSignalSource.TERM_RESOLVE_MISS, expression=" 势力 ",
        workspace_id="ws1", domain_id="d1", ref="resolver", detail="miss",
    )
    assert g1["heat"] == 1
    assert g1["expression"] == "势力"          # strip
    assert g1["scope_key"] == "ws1::d1"
    assert g1["status"] == GapStatus.OPEN.value
    g2 = store.record_signal(
        source=GapSignalSource.QA_UNANSWERED, expression="势力",
        workspace_id="ws1", domain_id="d1",
    )
    assert g2["id"] == g1["id"]                # 唯一索引去重
    assert g2["heat"] == 2
    assert g2["source_counts_json"]["term_resolve_miss"] == 1
    assert g2["source_counts_json"]["qa_unanswered"] == 1


def test_rejected_gap_revives_to_open_on_new_signal(store):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "军团",
                            workspace_id="ws1", domain_id="d1")
    store.update_status(g["id"], GapStatus.REJECTED.value, dismiss_reason="噪声")
    g2 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "军团",
                             workspace_id="ws1", domain_id="d1")
    assert g2["status"] == GapStatus.OPEN.value
    assert g2["heat"] == 2
    # 终审 n4：复活时清空陈旧 dismiss_reason（缺口重新 open，旧「忽略原因」不再适用）
    assert g2["dismiss_reason"] is None


def test_sources_capped_at_50(store):
    for i in range(60):
        store.record_signal(GapSignalSource.MAPPING_FAILURE, "诸侯",
                            workspace_id="ws1", domain_id="d1", ref=f"r{i}")
    g = store.get_by_expression("诸侯", "ws1::d1")
    assert len(g["sources_json"]) == 50
    assert g["heat"] == 60                     # 计数不丢


def test_list_gaps_filters_and_pagination(store):
    for expr in ("a", "b", "c"):
        store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, expr,
                            workspace_id="ws1", domain_id="d1")
    items, total = store.list_gaps(workspace_id="ws1", page=1, page_size=2)
    assert total == 3
    assert len(items) == 2


def test_get_missing_returns_none(store):
    assert store.get_gap("nope") is None


def test_bad_json_tolerated(store, monkeypatch):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "坏json",
                            workspace_id="ws1", domain_id="d1")
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE concept_gaps SET source_counts_json='{bad' WHERE id=?", (g["id"],))
    conn.commit()
    conn.close()
    got = store.get_gap(g["id"])
    assert got["source_counts_json"] == {}     # 坏 JSON 容错为空


def test_list_gaps_source_filter_pagination(store):
    """覆盖测试（规则 14.6）：source 过滤必须在 SQL 侧一致计算 total 与分页。

    修复前：total 由不含 source 的 WHERE 计算（over-count），SQL 先 LIMIT/OFFSET
    再 Python 侧按 source post-filter items，导致某页 under-return（甚至为空）。
    种子为混合来源且 source 过滤跨页边界，此测试必须在修复前失败、修复后通过。
    """
    ga = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "a",
                             workspace_id="ws1", domain_id="d1")
    gb = store.record_signal(GapSignalSource.QA_UNANSWERED, "b",
                             workspace_id="ws1", domain_id="d1")
    gc = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "c",
                             workspace_id="ws1", domain_id="d1")

    # (a) total 只数带该 source 的缺口（2，不是 3）；(c) 分页尊重过滤
    items1, total1 = store.list_gaps(source="term_resolve_miss", page=1, page_size=1)
    assert total1 == 2
    assert len(items1) == 1
    # (b) 返回页只含 source_counts_json 带该 source 的缺口
    assert items1[0]["source_counts_json"].get("term_resolve_miss")
    assert not items1[0]["source_counts_json"].get("qa_unanswered")

    # 第二页：修复前 post-filter 会把该页掏空（under-return）
    items2, total2 = store.list_gaps(source="term_resolve_miss", page=2, page_size=1)
    assert total2 == 2
    assert len(items2) == 1
    assert items2[0]["source_counts_json"].get("term_resolve_miss")
    assert not items2[0]["source_counts_json"].get("qa_unanswered")

    # 两页恰好覆盖两个 term_resolve_miss 缺口（a 和 c），绝不含 b
    assert {items1[0]["id"], items2[0]["id"]} == {ga["id"], gc["id"]}
    assert gb["id"] not in {items1[0]["id"], items2[0]["id"]}
