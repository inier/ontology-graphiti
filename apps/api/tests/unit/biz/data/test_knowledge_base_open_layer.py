"""ADR-084 F1/F3 回归：摄入车道 open/typed 双层 + 写前 USL 归一。

F1：`_write_to_graph` 曾把含中文类型名的实体塌缩成 `zh_type` 桶直写 Neo4j，
    绕过语义治理。整改后：未治理类型不再落 typed 图，改经 open 层转候选队列。
F3：写前经 UslTermResolver.canonical_of 归一类型，未命中打 unresolved_term。

测试策略（AGENTS.md 规则 9/14）：
  - `_partition_entities_by_type` 为纯函数，直接断言二分结果、且永不产生 zh_type。
  - `_stage_open_layer_entities` 用真实 tmp_path SQLite 候选库，断言候选落库。
  - 不用 MagicMock 模拟 DB。
"""

from __future__ import annotations

import pytest

from odap.biz.data.knowledge_base.services.knowledge_base_service import (
    KnowledgeBaseService,
)
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import (
    UslTermResolver,
)


@pytest.fixture
def svc(tmp_path):
    """KnowledgeBaseService，注入真实 tmp_path 候选库（不触 Neo4j）。"""
    cand_storage = SQLiteCandidateStorage(db_path=str(tmp_path / "cands.db"))
    # storage 传 None 会构造默认 KB 存储；这里只需 open 层相关方法，
    # 但为避免默认 KB 存储写到 DATA_DIR，仍给一个 tmp KB 库。
    from odap.biz.data.knowledge_base.storage.sqlite_kb_storage import (
        SQLiteKnowledgeBaseStorage,
    )
    kb_storage = SQLiteKnowledgeBaseStorage(db_path=str(tmp_path / "kb.db"))
    return KnowledgeBaseService(
        storage=kb_storage,
        candidate_storage=cand_storage,
    )


def _resolver_with(terms):
    r = UslTermResolver()
    r.load_terms("domain-x", terms)
    return r


# ======================================================================
# F1：_partition_entities_by_type —— 纯二分，永不产生 zh_type
# ======================================================================

class TestPartitionNoResolver:
    def test_ascii_type_goes_typed(self, svc):
        ents = [{"name": "Alice", "type": "Person"}]
        typed, open_layer = svc._partition_entities_by_type(ents)
        assert len(typed) == 1 and not open_layer
        assert typed[0][1] == "person"

    def test_chinese_type_goes_open_not_zh_type(self, svc):
        ents = [{"name": "孙悟空", "type": "人物"}]
        typed, open_layer = svc._partition_entities_by_type(ents)
        assert not typed
        assert len(open_layer) == 1
        assert open_layer[0]["raw_type"] == "人物"
        # 核心反向探针：绝不产生 zh_type 桶
        assert all("zh_type" not in str(item) for item in open_layer)

    def test_empty_type_goes_open(self, svc):
        ents = [{"name": "X", "type": ""}]
        typed, open_layer = svc._partition_entities_by_type(ents)
        assert not typed and len(open_layer) == 1

    def test_mixed_partition(self, svc):
        ents = [
            {"name": "Bob", "type": "Person"},
            {"name": "金箍棒", "type": "法器"},
            {"name": "Org", "type": "organization"},
        ]
        typed, open_layer = svc._partition_entities_by_type(ents)
        assert {e["name"] for e, _ in typed} == {"Bob", "Org"}
        assert {i["entity"]["name"] for i in open_layer} == {"金箍棒"}

    def test_never_emits_zh_type_across_many(self, svc):
        ents = [{"name": f"n{i}", "type": t}
                for i, t in enumerate(["人物", "地点", "事件", "Person", ""])]
        typed, open_layer = svc._partition_entities_by_type(ents)
        for _, type_id in typed:
            assert type_id != "zh_type"
        assert len(typed) == 1  # 仅 Person


# ======================================================================
# F3：写前 USL 归一
# ======================================================================

class TestPartitionWithResolver:
    def test_canonical_hit_ascii_goes_typed(self, svc):
        resolver = _resolver_with([
            {"canonical": "Person", "synonyms": ["人物", "角色"]},
        ])
        ents = [{"name": "孙悟空", "type": "人物"}]
        typed, open_layer = svc._partition_entities_by_type(
            ents, resolver=resolver, domain_id="domain-x",
        )
        # "人物" 归一到 ASCII canonical "Person" → typed 层
        assert len(typed) == 1 and typed[0][1] == "person"
        assert not open_layer

    def test_miss_marks_unresolved_and_goes_open(self, svc):
        resolver = _resolver_with([{"canonical": "Person", "synonyms": ["人物"]}])
        ents = [{"name": "未知物", "type": "法宝"}]
        typed, open_layer = svc._partition_entities_by_type(
            ents, resolver=resolver, domain_id="domain-x",
        )
        assert not typed
        assert len(open_layer) == 1
        assert open_layer[0]["unresolved_term"] is True
        assert open_layer[0]["canonical"] is None

    def test_canonical_hit_but_chinese_stays_open_with_canonical(self, svc):
        """归一命中但 canonical 仍是中文（非 ASCII 安全）→ 留 open 层，
        但记录 usl canonical 供治理晋升，不自由落图。"""
        resolver = _resolver_with([{"canonical": "法术", "synonyms": ["神通"]}])
        ents = [{"name": "七十二变", "type": "神通"}]
        typed, open_layer = svc._partition_entities_by_type(
            ents, resolver=resolver, domain_id="domain-x",
        )
        assert not typed
        assert open_layer[0]["canonical"] == "法术"
        assert open_layer[0]["unresolved_term"] is False  # 命中了，只是非 ASCII


# ======================================================================
# F1：_stage_open_layer_entities —— 真实 tmp_path 候选库落库
# ======================================================================

class TestStageOpenLayer:
    def test_stages_candidates_with_provenance(self, svc):
        open_items = [
            {"entity": {"name": "孙悟空", "type": "人物"},
             "raw_type": "人物", "canonical": None, "unresolved_term": True},
            {"entity": {"name": "金箍棒", "type": "法器"},
             "raw_type": "法器", "canonical": None, "unresolved_term": True},
        ]
        ids = svc._stage_open_layer_entities(open_items, "kb1", "doc1", "ws1")
        assert len(ids) == 2

        listed = svc._candidate_storage.list_candidates(page=1, page_size=50)
        items = listed.get("items") if isinstance(listed, dict) else listed[0]
        assert len(items) == 2
        by_name = {c["canonical"]: c for c in items}
        assert set(by_name) == {"孙悟空", "金箍棒"}
        c = by_name["孙悟空"]
        assert c["origin"] == "llm"
        prov = c.get("provenance") or {}
        assert prov.get("open_layer") is True
        assert prov.get("source") == "kb_ingest_open_layer"
        assert prov.get("raw_type") == "人物"
        assert prov.get("unresolved_term") is True
        assert prov.get("kb_id") == "kb1" and prov.get("doc_id") == "doc1"

    def test_empty_open_items_no_run_created(self, svc):
        ids = svc._stage_open_layer_entities([], "kb1", "doc1")
        assert ids == []

    def test_entities_without_name_skipped(self, svc):
        open_items = [
            {"entity": {"name": "", "type": "人物"},
             "raw_type": "人物", "canonical": None, "unresolved_term": True},
        ]
        ids = svc._stage_open_layer_entities(open_items, "kb1", "doc1")
        assert ids == []

    def test_run_source_type_is_ingest(self, svc):
        open_items = [
            {"entity": {"name": "孙悟空", "type": "人物"},
             "raw_type": "人物", "canonical": None, "unresolved_term": True},
        ]
        svc._stage_open_layer_entities(open_items, "kb1", "doc1", "ws1")
        runs = svc._candidate_storage.list_pipeline_runs(page=1, page_size=10)
        run_items = runs.get("items") if isinstance(runs, dict) else runs[0]
        assert any(r.get("source_type") == "ingest" for r in run_items)
