"""子项目 A：gap_pool 归因分层 —— 存储层测试（真实 tmp_path DB，规则 9/14.6）。

覆盖：旧库（无 attribution 列）自动 ALTER 迁移且幂等；attribution 计数累加；
occurrence 截断后 attribution 键仍在最近 50 条内；layer 过滤与 total 同源；
坏 JSON 回退 {}；不带 attribution 的调用（旧签名路径）行为不变。
"""
import sqlite3

import pytest
from odap.biz.semantic_admin.gap_pool.models import (
    GapLayer, GapSignalSource, GapStatus,
)
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


_CONTENT_ATTR = {"layer": GapLayer.CONTENT.value,
                 "target_kind": "term", "target_ref": "诸侯"}
_TOOL_ATTR = {"layer": GapLayer.TOOL.value,
              "target_kind": "engine", "target_ref": "nl_engine"}


# ── 旧库迁移（E-a） ─────────────────────────────────────────────────────

def test_old_db_without_attribution_column_migrates(tmp_path):
    """旧 schema（无 attribution_counts_json 列）启动即 ALTER 加列，幂等可重复。"""
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE concept_gaps (
            id TEXT PRIMARY KEY, expression TEXT NOT NULL, scope_key TEXT NOT NULL,
            heat INTEGER NOT NULL DEFAULT 1,
            source_counts_json TEXT NOT NULL DEFAULT '{}',
            sources_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'open',
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, updated_at TEXT NOT NULL,
            promoted_candidate_id TEXT, resolved_term_id TEXT, dismiss_reason TEXT,
            workspace_id TEXT, domain_id TEXT
        );
        INSERT INTO concept_gaps VALUES (
            'g1', '旧词', 'ws1::d1', 3, '{"term_resolve_miss": 3}', '[]', 'open',
            '2026-10-08T00:00:00+00:00', '2026-10-08T00:00:00+00:00',
            '2026-10-08T00:00:00+00:00', NULL, NULL, NULL, 'ws1', 'd1'
        );
        """
    )
    conn.commit()
    conn.close()

    s = SQLiteGapStorage(db_path=db)          # 首次启动 → 迁移
    got = s.get_gap("g1")
    assert got is not None                     # 既有数据完好
    assert got["attribution_counts_json"] == {}  # 旧数据 NULL → 回退 {}
    assert got["heat"] == 3
    # ADR-090 子项目 D：两条 promote 路由回填列也被幂等迁入（旧行为=NULL）
    assert got["promoted_proposal_id"] is None
    assert got["promoted_ticket_id"] is None

    s2 = SQLiteGapStorage(db_path=db)          # 二次启动 → 幂等不报错
    assert s2.get_gap("g1")["heat"] == 3


def test_layer_column_exists_in_fresh_db(store):
    conn = sqlite3.connect(store.db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(concept_gaps)").fetchall()]
    conn.close()
    assert "attribution_counts_json" in cols
    assert "promoted_proposal_id" in cols
    assert "promoted_ticket_id" in cols


def test_sanitize_keeps_parent_key_for_schema_property(store):
    """ADR-090：schema 层 property 缺口需保留 parent 用于 RFC 6902 路径推导。"""
    g = store.record_signal(
        GapSignalSource.MAPPING_FAILURE, "寿命",
        workspace_id="ws1", domain_id="d1",
        attribution={"layer": "schema", "target_kind": "property",
                     "parent": "人物", "unknown_key": "丢"},
    )
    attr = g["sources_json"][-1]["attribution"]
    assert attr["parent"] == "人物"
    assert "unknown_key" not in attr


# ── attribution 计数累加（双层结构，E-b） ────────────────────────────────

def test_record_signal_accumulates_attribution_counts(store):
    g1 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                             workspace_id="ws1", domain_id="d1",
                             attribution=_CONTENT_ATTR)
    assert g1["attribution_counts_json"] == {"content": 1}
    g2 = store.record_signal(GapSignalSource.MAPPING_FAILURE, "诸侯",
                             workspace_id="ws1", domain_id="d1",
                             attribution=_CONTENT_ATTR)
    assert g2["heat"] == 2
    assert g2["attribution_counts_json"] == {"content": 2}
    # 混层：同 expression 再来一条 tool 层
    g3 = store.record_signal(GapSignalSource.NL_QUERY_UNANSWERED, "诸侯",
                             workspace_id="ws1", domain_id="d1",
                             attribution=_TOOL_ATTR)
    assert g3["attribution_counts_json"] == {"content": 2, "tool": 1}


def test_occurrence_carries_attribution_key(store):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            workspace_id="ws1", domain_id="d1",
                            attribution=_CONTENT_ATTR)
    occ = g["sources_json"][-1]
    assert occ["attribution"]["layer"] == "content"
    assert occ["attribution"]["target_kind"] == "term"
    assert occ["attribution"]["target_ref"] == "诸侯"


def test_record_signal_without_attribution_keeps_old_behavior(store):
    """旧签名路径（attribution=None）：occurrence 不带归因、计数不增、行为不变。"""
    g1 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                             workspace_id="ws1", domain_id="d1")
    assert g1["attribution_counts_json"] == {}
    assert "attribution" not in g1["sources_json"][-1]
    # 带归因后再来一条无归因的：计数保持、heat 仍 +1
    g2 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                             workspace_id="ws1", domain_id="d1",
                             attribution=_CONTENT_ATTR)
    g3 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                             workspace_id="ws1", domain_id="d1")
    assert g3["heat"] == 3
    assert g3["attribution_counts_json"] == {"content": 1}


def test_invalid_attribution_ignored_not_fabricated(store, monkeypatch):
    """规则 14 不造数：layer 非法 / 非 dict 的 attribution 视为无归因（warning 可观测）。"""
    import logging as _logging
    from odap.biz.semantic_admin.gap_pool.storage import sqlite_gap_storage as mod
    records = []
    handler = _logging.Handler()
    handler.emit = lambda r: records.append(r)
    lg = _logging.getLogger(mod.__name__)
    lg.addHandler(handler)

    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            workspace_id="ws1", domain_id="d1",
                            attribution={"layer": "bogus", "target_kind": "term"})
    assert g["attribution_counts_json"] == {}      # 不造数
    assert any(r.levelno >= _logging.WARNING for r in records)  # 可观测

    g2 = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "阵营",
                             workspace_id="ws1", domain_id="d1",
                             attribution="not-a-dict")
    assert g2["attribution_counts_json"] == {}
    lg.removeHandler(handler)


def test_sources_cap_keeps_attribution_in_latest_50(store):
    for i in range(60):
        store.record_signal(GapSignalSource.MAPPING_FAILURE, "诸侯",
                            workspace_id="ws1", domain_id="d1",
                            attribution=_CONTENT_ATTR)
    g = store.get_by_expression("诸侯", "ws1::d1")
    assert len(g["sources_json"]) == 50
    assert all(o.get("attribution", {}).get("layer") == "content"
               for o in g["sources_json"])
    assert g["attribution_counts_json"] == {"content": 60}   # 全量计数不丢


# ── layer 过滤（与 source 过滤同模式，total 与分页同源） ─────────────────

def test_list_gaps_layer_filter(store):
    store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "a",
                        workspace_id="ws1", domain_id="d1",
                        attribution=_CONTENT_ATTR)
    store.record_signal(GapSignalSource.QA_UNANSWERED, "b",
                        workspace_id="ws1", domain_id="d1",
                        attribution=_TOOL_ATTR)
    store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "c",
                        workspace_id="ws1", domain_id="d1")   # 无归因

    items, total = store.list_gaps(layer="content", page=1, page_size=10)
    assert total == 1                              # 只有 a
    assert items[0]["expression"] == "a"

    items_tool, total_tool = store.list_gaps(layer="tool", page=1, page_size=10)
    assert total_tool == 1
    assert items_tool[0]["expression"] == "b"

    # 无归因缺口不出现在任何 layer 过滤里
    all_filtered = {i["expression"] for i in items} | {i["expression"] for i in items_tool}
    assert "c" not in all_filtered


def test_count_by_layer(store):
    store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "a",
                        workspace_id="ws1", domain_id="d1",
                        attribution=_CONTENT_ATTR)
    store.record_signal(GapSignalSource.QA_UNANSWERED, "b",
                        workspace_id="ws1", domain_id="d1",
                        attribution=_TOOL_ATTR)
    store.record_signal(GapSignalSource.MAPPING_FAILURE, "a",
                        workspace_id="ws1", domain_id="d1",
                        attribution=_CONTENT_ATTR)
    assert store.count_by_layer() == {"content": 2, "tool": 1}


# ── 坏 JSON 容错 ────────────────────────────────────────────────────────

def test_bad_attribution_json_tolerated(store):
    g = store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "坏json",
                            workspace_id="ws1", domain_id="d1",
                            attribution=_CONTENT_ATTR)
    conn = sqlite3.connect(store.db_path)
    conn.execute(
        "UPDATE concept_gaps SET attribution_counts_json='{bad' WHERE id=?",
        (g["id"],),
    )
    conn.commit()
    conn.close()
    got = store.get_gap(g["id"])
    assert got["attribution_counts_json"] == {}     # 坏 JSON 容错为空
