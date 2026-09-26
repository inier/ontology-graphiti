"""结构化语义抽取链路回归测试（semantic_asset_pipeline 链路 A）。

历史缺陷：`_collect_structured_candidates` 曾读 `ingest_result["entities"] /
["items"]`，而 `UnifiedIngestFacade.ingest` 只返回
`{"status", "source_type", "record_id", "routed_to"}` —— 这两个键从不存在。
于是 14 种结构化源（url/news/tavily/manual/json/random_events/database/
kb_upload/ontology_document/webhook/sensor/mcp/file/api）全部「引入成功、
候选恒为 0」，却照报 status=ok，前端显示"成功、0 条候选"，业务人员永远
等不到待审语义（AGENTS.md 规则 14：静默假成功）。

真实产物在别处：`_DocumentProcessor.process` 会把整个 `OntologyDocument`
（entities/relations/events/actions/rules/constraints 全量）写进
`ontology_documents` 表，摄入记录的 `extracted_data.document_ids` 就是索引。
注意 `extracted_data` 里的 `entities/relations/events` 是**计数**（int），
不是清单 —— 这正是原实现误读的地方。

测试原则（规则 14 要求 6）：不 patch 被测函数体。摄入侧走真实
`SQLiteIngestStorage` + 真实 `OntologyDocument` 序列化往返（tmp_path 真库），
只跳过 `UnifiedIngestionService` 那层会连 Neo4j/Graphiti 的重构造。
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

_ROOT = Path(__file__).resolve().parents[4]
_PIPELINE_SERVICE_PY = (
    _ROOT / "apps" / "api" / "odap" / "biz" / "semantic_admin"
    / "semantic_asset_pipeline" / "services" / "pipeline_service.py"
)

_PIPELINE_MOD = (
    "odap.biz.semantic_admin.semantic_asset_pipeline.services.pipeline_service"
)
_DOC_MOD = "odap.biz.core.ontology.design.schema.document"


# ──────────────────────────────────────────────────────────────────────
# 摄入侧适配器：真库真表，只替换会连外部服务的重构造
# ──────────────────────────────────────────────────────────────────────
class _IngestReadOnlyAdapter:
    """把真实 SQLiteIngestStorage 适配成 UnifiedIngestionService 的只读查询面。

    只实现被测代码实际调用的两个方法；多实现一个就会掩盖「被测代码偷偷依赖了
    别的能力」这类问题。
    """

    def __init__(self, storage) -> None:
        self._storage = storage

    def get_ingest_status(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_ingest_record(ingest_id)

    def get_ontology_document(self, doc_id: str):
        return self._storage.get_ontology_document(doc_id)


@pytest.fixture
def ingest_storage(tmp_path):
    from odap.biz.core.ontology.design.storage.sqlite_ingest_storage import (
        SQLiteIngestStorage,
    )
    return SQLiteIngestStorage(db_path=str(tmp_path / "ingest.db"))


@pytest.fixture
def pipeline(tmp_path, ingest_storage):
    from importlib import import_module

    mod = import_module(_PIPELINE_MOD)
    from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
        SQLiteCandidateStorage,
    )

    p = mod.SemanticAssetPipeline()
    # 注入真库，绕开 DATA_DIR / CWD 默认路径（规则 13：不往项目根写文件）
    p._ingest_service = _IngestReadOnlyAdapter(ingest_storage)
    p._candidate_storage = SQLiteCandidateStorage(
        db_path=str(tmp_path / "candidate_store.db")
    )
    return p


# ──────────────────────────────────────────────────────────────────────
# 造数工具
# ──────────────────────────────────────────────────────────────────────
def _make_doc(
    doc_id: str,
    *,
    entities=(),
    relations=(),
    events=(),
    actions=(),
    rules=(),
    constraints=(),
    scenario_id: str = "sc-test",
    ontology_id: Optional[str] = "ont-test",
):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    return d.OntologyDocument(
        doc_id=doc_id,
        doc_type=d.DocType.EVENT.value,
        scenario_id=scenario_id,
        ontology_id=ontology_id,
        entities=list(entities),
        relations=list(relations),
        events=list(events),
        actions=list(actions),
        rules=list(rules),
        constraints=list(constraints),
    )


def _entity(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "entity_type": "Unit",
        "name": "红方装甲营",
        "name_en": "Red Armor Battalion",
        "aliases": ["红装甲", "Red Armor"],
        "basic_properties": {"description": "红方主力装甲部队", "side": "Red"},
        "statistical_properties": {"personnel": 420},
    }
    kwargs.update(overrides)
    return d.OntologyEntity(**kwargs)


def _relation(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "relation_type": "隶属于",
        "source_entity": "红方装甲营",
        "target_entity": "红方第1师",
    }
    kwargs.update(overrides)
    return d.OntologyRelation(**kwargs)


def _event(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "event_type": "装甲推进",
        "timestamp": "2026-09-01T08:00:00Z",
        "description": "红方装甲营向蓝方阵地推进",
        "participants": ["红方装甲营", "蓝方守备连"],
    }
    kwargs.update(overrides)
    return d.OntologyEvent(**kwargs)


def _action(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "action_type": "下达进攻命令",
        "actor": "红方指挥部",
        "target": "红方装甲营",
        "opa_required": True,
    }
    kwargs.update(overrides)
    return d.OntologyAction(**kwargs)


def _rule(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "rule_type": "交战规则",
        "description": "禁止攻击民用设施",
        "condition": "目标类型 == 民用",
        "consequence": "拒绝执行",
        "priority": "high",
    }
    kwargs.update(overrides)
    return d.OntologyRule(**kwargs)


def _constraint(**overrides):
    from importlib import import_module

    d = import_module(_DOC_MOD)
    kwargs: Dict[str, Any] = {
        "constraint_type": "legal",
        "description": "受日内瓦公约约束",
        "legal_basis": "Geneva Convention",
    }
    kwargs.update(overrides)
    return d.OntologyConstraint(**kwargs)


def _seed_record(
    ingest_storage,
    record_id: str,
    doc_ids: List[str],
    *,
    status: str = "completed",
    extra_extracted: Optional[Dict[str, Any]] = None,
) -> None:
    """写入一条真实摄入记录。

    `extracted_data` 刻意带上 entities/relations/events 三个 **int 计数**，
    与真实 `ingest_from_*` 的产出一致 —— 用来证明新实现不会把计数当清单读。
    """
    extracted: Dict[str, Any] = {
        "document_ids": list(doc_ids),
        "document_count": len(doc_ids),
        "entities": 3,
        "relations": 1,
        "events": 1,
    }
    if extra_extracted:
        extracted.update(extra_extracted)
    ingest_storage.save_ingest_record({
        "id": record_id,
        "source": "manual",
        "status": status,
        "record_count": len(doc_ids),
        "processed_count": len(doc_ids),
        "failed_count": 0,
        "start_time": "2026-09-01T00:00:00",
        "end_time": "2026-09-01T00:01:00",
        "duration_seconds": 60.0,
        "extracted_data": extracted,
        "original_content": "原始文本",
        "created_by": "tester",
        "scenario_id": "sc-test",
    })


def _by_type(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        out.setdefault(r["semantic_type"], []).append(r)
    return out


def _persisted(pipeline, run_id: str) -> List[Dict[str, Any]]:
    """从真实 candidate_store 库回读，验证「报了 N 条」等于「库里真有 N 条」。"""
    res = pipeline.candidate_storage.list_candidates(
        run_id=run_id, page=1, page_size=500,
    )
    if isinstance(res, tuple):
        items, _total = res
    elif isinstance(res, dict):
        items = list(res.get("items") or [])
    else:
        items = []
    return items


# ──────────────────────────────────────────────────────────────────────
# 1. 五类语义映射 + 属性槽位
# ──────────────────────────────────────────────────────────────────────
class TestStructuredSemanticMapping:
    def test_all_five_sections_map_to_usl_semantic_types(
        self, pipeline, ingest_storage,
    ):
        doc = _make_doc(
            "doc-full",
            entities=[_entity()],
            relations=[_relation()],
            events=[_event()],
            actions=[_action()],
            rules=[_rule()],
            constraints=[_constraint()],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-full", ["doc-full"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-full"},
            run_id="run-1", ontology_id="ont-test", source_kind="structured",
        )

        assert out["status"] == "ok", out
        grouped = _by_type(out["records"])
        assert grouped["对象类型"][0]["canonical"] == "红方装甲营"
        assert grouped["关系类型"][0]["canonical"] == "隶属于"
        assert grouped["过程类型"][0]["canonical"] == "装甲推进"
        assert grouped["动作类型"][0]["canonical"] == "下达进攻命令"
        assert grouped["规则类型"][0]["canonical"] == "交战规则"

        obj = grouped["对象类型"][0]
        assert obj["en"] == "Red Armor Battalion"
        assert obj["synonyms"] == ["红装甲", "Red Armor"]
        assert obj["definition"] == "红方主力装甲部队"
        assert obj["origin"] == "structured"
        assert obj["confidence"] == 1.0
        assert obj["provenance"]["ingest_record_id"] == "rec-full"
        assert obj["provenance"]["doc_id"] == "doc-full"
        assert obj["provenance"]["entity_type"] == "Unit"

        assert grouped["关系类型"][0]["source_text"] == (
            "红方装甲营 --[隶属于]--> 红方第1师"
        )
        assert grouped["动作类型"][0]["source_text"] == (
            "红方指挥部 执行 下达进攻命令 → 红方装甲营"
        )
        assert grouped["动作类型"][0]["provenance"]["opa_required"] is True
        assert grouped["规则类型"][0]["source_text"] == (
            "若 目标类型 == 民用 则 拒绝执行"
        )
        assert grouped["过程类型"][0]["provenance"]["participants"] == [
            "红方装甲营", "蓝方守备连",
        ]

    def test_entity_property_slots_become_attribute_candidates(
        self, pipeline, ingest_storage,
    ):
        doc = _make_doc(
            "doc-attrs",
            entities=[_entity(
                basic_properties={"description": "x", "side": "Red", "status": "战备"},
                statistical_properties={"personnel": 420, "tanks": 30},
            )],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-attrs", ["doc-attrs"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-attrs"},
            run_id="run-attrs", ontology_id="ont-test", source_kind="structured",
        )

        assert out["status"] == "ok", out
        attrs = _by_type(out["records"])["属性"]
        names = {(a["canonical"], a["provenance"]["property_group"]) for a in attrs}
        assert ("side", "basic_properties") in names
        assert ("status", "basic_properties") in names
        assert ("personnel", "statistical_properties") in names
        assert ("tanks", "statistical_properties") in names
        # description 已是对象类型的 definition，但仍作为属性槽位保留，
        # 由业务人员在审核时决定是否停用
        assert ("description", "basic_properties") in names
        assert all(a["provenance"]["attribute_of"] == "红方装甲营" for a in attrs)

    def test_constraints_are_not_force_fitted_into_a_usl_type(
        self, pipeline, ingest_storage,
    ):
        """USL 6 类里没有「约束」，硬塞等于猜测性归类（规则 14 要求 4）。"""
        doc = _make_doc("doc-cst", constraints=[_constraint()])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-cst", ["doc-cst"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-cst"},
            run_id="run-cst", ontology_id="ont-test", source_kind="structured",
        )

        assert out["status"] == "ok", out
        assert out["records"] == []
        assert out["stats"]["documents"] == 1
        assert out["stats"]["deduped_candidates"] == 0

    def test_all_emitted_semantic_types_are_usl_legal(
        self, pipeline, ingest_storage,
    ):
        """落库前必须都是 USL 合法语义类型，否则候选进不了审核队列。"""
        from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
            VALID_SEMANTIC_TYPES,
        )

        doc = _make_doc(
            "doc-legal",
            entities=[_entity()], relations=[_relation()], events=[_event()],
            actions=[_action()], rules=[_rule()],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-legal", ["doc-legal"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-legal"},
            run_id="run-legal", ontology_id="ont-test", source_kind="structured",
        )
        emitted = {r["semantic_type"] for r in out["records"]}
        assert emitted, "归集结果为空，链路仍是断的"
        assert emitted <= VALID_SEMANTIC_TYPES, emitted - VALID_SEMANTIC_TYPES

    def test_int_counts_in_extracted_data_are_not_read_as_entities(
        self, pipeline, ingest_storage,
    ):
        """历史缺陷回归闸：`entities: 3` 是计数，绝不能产出名为 "3" 的候选。"""
        doc = _make_doc("doc-counts", entities=[_entity(name="唯一实体")])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-counts", ["doc-counts"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-counts"},
            run_id="run-counts", ontology_id="ont-test", source_kind="structured",
        )
        canonicals = {r["canonical"] for r in out["records"]}
        assert "3" not in canonicals
        assert "1" not in canonicals
        assert "唯一实体" in canonicals


# ──────────────────────────────────────────────────────────────────────
# 2. 跨文档去重与同义词合并
# ──────────────────────────────────────────────────────────────────────
class TestCrossDocumentDedup:
    def test_same_entity_in_two_documents_yields_one_candidate(
        self, pipeline, ingest_storage,
    ):
        d1 = _make_doc("doc-a", entities=[_entity(
            name="红方装甲营", aliases=["红装甲"],
            basic_properties={"side": "Red"},
        )])
        d2 = _make_doc("doc-b", entities=[_entity(
            name="红方装甲营", aliases=["Red Armor"], name_en="",
            basic_properties={"description": "后补的定义", "side": "Red"},
        )])
        ingest_storage.save_ontology_document(d1)
        ingest_storage.save_ontology_document(d2)
        _seed_record(ingest_storage, "rec-dedup", ["doc-a", "doc-b"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-dedup"},
            run_id="run-dedup", ontology_id="ont-test", source_kind="structured",
        )

        objs = [r for r in out["records"] if r["semantic_type"] == "对象类型"]
        assert len(objs) == 1, objs
        merged = objs[0]
        # 同义词并集且去重保序
        assert merged["synonyms"] == ["红装甲", "Red Armor"]
        # 首个文档没有 description，第二个补上 → 空字段被填充
        assert merged["definition"] == "后补的定义"
        # en 同理
        assert merged["en"] == "Red Armor Battalion"
        assert merged["provenance"]["doc_id"] == "doc-a"
        assert merged["provenance"]["merged_doc_ids"] == ["doc-b"]

        stats = out["stats"]
        assert stats["documents"] == 2
        assert stats["raw_items"] > stats["deduped_candidates"]
        assert stats["by_semantic_type"]["对象类型"] == 2

    def test_same_name_different_type_is_not_deduped(
        self, pipeline, ingest_storage,
    ):
        """去重键是 (semantic_type, canonical)，不是 canonical 本身。"""
        doc = _make_doc(
            "doc-key",
            entities=[_entity(name="推进")],
            events=[_event(event_type="推进", description="")],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-key", ["doc-key"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-key"},
            run_id="run-key", ontology_id="ont-test", source_kind="structured",
        )
        hits = [r for r in out["records"] if r["canonical"] == "推进"]
        assert {h["semantic_type"] for h in hits} == {"对象类型", "过程类型"}

    def test_blank_names_are_skipped(self, pipeline, ingest_storage):
        doc = _make_doc(
            "doc-blank",
            entities=[_entity(name="   "), _entity(name="有名实体")],
            relations=[_relation(relation_type="")],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-blank", ["doc-blank"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-blank"},
            run_id="run-blank", ontology_id="ont-test", source_kind="structured",
        )
        canonicals = {r["canonical"] for r in out["records"]}
        assert "有名实体" in canonicals
        assert "" not in canonicals
        assert "   " not in canonicals


# ──────────────────────────────────────────────────────────────────────
# 3. 落库：报了 N 条就必须库里真有 N 条
# ──────────────────────────────────────────────────────────────────────
class TestCandidatesAreReallyPersisted:
    def test_reported_records_match_candidate_store(self, pipeline, ingest_storage):
        doc = _make_doc(
            "doc-persist",
            entities=[_entity()], relations=[_relation()], events=[_event()],
            actions=[_action()], rules=[_rule()],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-persist", ["doc-persist"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-persist"},
            run_id="run-persist", ontology_id="ont-test", source_kind="structured",
        )
        assert out["status"] == "ok", out

        rows = _persisted(pipeline, "run-persist")
        assert len(rows) == len(out["records"]) == out["stats"]["deduped_candidates"]
        assert {r["canonical"] for r in rows} == {
            r["canonical"] for r in out["records"]
        }
        # 结构化候选必须落回 DRAFT（读路径按过渡约定暴露旧小写枚举 "new"），
        # 否则 submit() 会全部 skip，业务人员永远看不到待审语义。
        from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
            CAND_DRAFT,
        )
        norm = pipeline.candidate_storage._norm_cand_status
        assert all(norm(r.get("status")) == CAND_DRAFT for r in rows), [
            (r["canonical"], r.get("status")) for r in rows
        ]

    def test_collected_candidates_can_be_submitted_for_review(
        self, pipeline, ingest_storage,
    ):
        """用户核心诉求的闭环闸：抽取出的业务语义必须真能提交业务审核。"""
        doc = _make_doc(
            "doc-submit",
            entities=[_entity(name="甲实体"), _entity(name="乙实体")],
            relations=[_relation(relation_type="甲乙关系")],
            rules=[_rule(rule_type="甲乙规则")],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-submit", ["doc-submit"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-submit"},
            run_id="run-submit", ontology_id="ont-test", source_kind="structured",
        )
        assert out["status"] == "ok", out
        expected = len(out["records"])
        assert expected >= 4, out["records"]

        res = pipeline.submit("run-submit", actor="biz-user")
        assert res["status"] == "ok", res
        assert res["submitted"] == expected, res
        assert res["skipped"] == 0, res

        from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
            CAND_PENDING_REVIEW,
        )
        norm = pipeline.candidate_storage._norm_cand_status
        rows = _persisted(pipeline, "run-submit")
        assert rows and all(
            norm(r.get("status")) == CAND_PENDING_REVIEW for r in rows
        ), [(r["canonical"], r.get("status")) for r in rows]

    def test_bulk_insert_failure_is_an_error_not_a_silent_success(
        self, pipeline, ingest_storage, monkeypatch,
    ):
        """落库失败却报 status=ok + candidate_count>0，get_run 再查一条都没有。"""
        doc = _make_doc("doc-fail", entities=[_entity()])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-fail", ["doc-fail"])

        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-fail"},
            run_id="run-fail", ontology_id="ont-test", source_kind="structured",
        )
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert "未持久化" in out["message"]
        assert _persisted(pipeline, "run-fail") == []


# ──────────────────────────────────────────────────────────────────────
# 4. 回捞失败必须显式，不得静默返回 0 条候选
# ──────────────────────────────────────────────────────────────────────
class TestResolveFailuresAreExplicit:
    def test_missing_record_id_is_explicit_error(self, pipeline):
        out = pipeline._collect_structured_candidates(
            {"status": "ok", "routed_to": "IngestService"},
            run_id="run-x", ontology_id=None, source_kind="structured",
        )
        assert out["status"] == "error"
        assert "record_id" in out["message"]
        # 必须把实际返回的键打出来，否则排查时只能猜
        assert "routed_to" in out["message"]

    def test_unknown_record_is_explicit_error(self, pipeline):
        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-does-not-exist"},
            run_id="run-x", ontology_id=None, source_kind="structured",
        )
        assert out["status"] == "error"
        assert "rec-does-not-exist" in out["message"]

    def test_empty_document_ids_is_explicit_error(self, pipeline, ingest_storage):
        """事件通道（webhook/sensor/mcp/file/api）不产出 OntologyDocument。"""
        _seed_record(ingest_storage, "rec-empty", [])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-empty"},
            run_id="run-x", ontology_id=None, source_kind="structured",
        )
        assert out["status"] == "error"
        assert "document_ids" in out["message"]

    def test_event_id_is_accepted_as_record_key(self, pipeline, ingest_storage):
        doc = _make_doc("doc-ev", entities=[_entity(name="事件实体")])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "evt-1", ["doc-ev"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "event_id": "evt-1"},
            run_id="run-ev", ontology_id=None, source_kind="structured",
        )
        assert out["status"] == "ok", out
        assert any(r["canonical"] == "事件实体" for r in out["records"])

    def test_unreadable_document_surfaces_warning_not_silent_drop(
        self, pipeline, ingest_storage,
    ):
        """记录声明 2 个文档但只存了 1 个 —— 结果不完整，必须留痕。"""
        doc = _make_doc("doc-ok", entities=[_entity(name="读得回的实体")])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-partial", ["doc-ok", "doc-gone"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-partial"},
            run_id="run-partial", ontology_id=None, source_kind="structured",
        )
        # 能读回的部分仍然归集成功，但不许假装完整
        assert out["status"] == "ok", out
        assert out["stats"]["documents"] == 1
        assert out["warnings"], "部分文档读不回却没有告警"
        assert "doc-gone" in out["warnings"][0]

    def test_documents_survive_sqlite_round_trip(self, pipeline, ingest_storage):
        """get_ontology_document 用位置索引 row[1]/row[5]... 解析 SELECT *，
        表列序一变就会静默错位。这条测试把往返钉死。"""
        doc = _make_doc(
            "doc-roundtrip",
            entities=[_entity(name="往返实体", aliases=["rt"])],
            relations=[_relation(relation_type="往返关系")],
            events=[_event(event_type="往返事件")],
            actions=[_action(action_type="往返动作")],
            rules=[_rule(rule_type="往返规则")],
        )
        ingest_storage.save_ontology_document(doc)

        back = ingest_storage.get_ontology_document("doc-roundtrip")
        assert back is not None
        assert back.doc_id == "doc-roundtrip"
        assert [e.name for e in back.entities] == ["往返实体"]
        assert [e.aliases for e in back.entities] == [["rt"]]
        assert [r.relation_type for r in back.relations] == ["往返关系"]
        assert [r.source_entity for r in back.relations] == ["红方装甲营"]
        assert [e.event_type for e in back.events] == ["往返事件"]
        assert [a.action_type for a in back.actions] == ["往返动作"]
        assert [r.rule_type for r in back.rules] == ["往返规则"]


# ──────────────────────────────────────────────────────────────────────
# 5. run() 端到端：归集失败必须冒泡到调用方
# ──────────────────────────────────────────────────────────────────────
class TestRunStructuredPropagatesFailure:
    async def test_run_reports_error_when_collection_fails(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "record_id": "rec-never-saved", "routed_to": "IngestService",
                }

        pipeline._ingest_facade = _Facade()

        res = await pipeline.run(
            source_type="manual", payload={"form_data": "x"},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "error", res
        assert "未能归集业务语义候选" in res["message"]
        # 引入本身成功了，调用方需要 record_id 才能补救
        assert res["ingest"]["record_id"] == "rec-never-saved"

    async def test_run_returns_candidates_and_stats_on_success(
        self, pipeline, ingest_storage,
    ):
        doc = _make_doc(
            "doc-run",
            entities=[_entity(name="跑通实体")],
            relations=[_relation(relation_type="跑通关系")],
        )
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-run", ["doc-run"])

        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "record_id": "rec-run", "routed_to": "IngestService",
                }

        pipeline._ingest_facade = _Facade()

        res = await pipeline.run(
            source_type="manual", payload={"form_data": "x"},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "ok", res
        assert res["source_kind"] == "structured"
        assert res["candidate_count"] == len(res["candidates"]) > 0
        assert res["collection_stats"]["documents"] == 1
        assert _persisted(pipeline, res["pipeline_run_id"])

    async def test_ingest_error_is_passed_through(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {"status": "error", "message": "抓取失败"}

        pipeline._ingest_facade = _Facade()
        res = await pipeline.run(source_type="url", payload={"url": "http://x"})
        assert res["status"] == "error"
        assert res["message"] == "抓取失败"


# ──────────────────────────────────────────────────────────────────────
# 6. _count_ontology_types：失败不再塌成 0
# ──────────────────────────────────────────────────────────────────────
class TestCountOntologyTypesNoSilentZero:
    def test_missing_method_is_reported_not_counted_as_zero(self, pipeline):
        class _Partial:
            def list_object_types(self, oid):
                return {"status": "ok", "object_types": [{"type_id": "t1"}], "count": 1}

        counts, errors = _call_count_with(pipeline, _Partial(), "ont-1")

        assert counts == {"object_types": 1}
        # 缺席的 4 类必须逐条报错，而不是写 0
        assert "object_types" not in " ".join(errors)
        for kind in ("link_types", "action_types", "process_types", "rule_types"):
            assert kind not in counts
            assert any(kind in e for e in errors), (kind, errors)

    def test_callee_error_status_is_surfaced(self, pipeline):
        class _Err:
            def list_object_types(self, oid):
                return {"status": "error", "message": "本体不存在"}

            def list_link_types(self, oid):
                return {"status": "ok", "link_types": [], "count": 0}

            def list_action_types(self, oid):
                return {"status": "ok", "action_types": [], "count": 0}

            def list_process_types(self, oid):
                return {"status": "ok", "process_types": [], "count": 0}

            def list_rule_types(self, oid):
                return {"status": "ok", "rule_types": [], "count": 0}

        counts, errors = _call_count_with(pipeline, _Err(), "ont-1")
        assert "object_types" not in counts
        assert counts["link_types"] == 0
        assert any("本体不存在" in e for e in errors), errors

    def test_count_field_is_the_only_accepted_shape(self, pipeline):
        class _Counted:
            def list_object_types(self, oid):
                return {"status": "ok", "count": 7}

            def list_link_types(self, oid):
                return {"status": "ok", "count": 0}

            def list_action_types(self, oid):
                return {"status": "ok", "count": 2}

            def list_process_types(self, oid):
                return {"status": "ok", "count": 0}

            def list_rule_types(self, oid):
                return {"status": "ok", "count": 3}

        counts, errors = _call_count_with(pipeline, _Counted(), "ont-1")
        assert counts == {
            "object_types": 7, "link_types": 0, "action_types": 2,
            "process_types": 0, "rule_types": 3,
        }
        assert errors == []

    def test_missing_count_field_is_an_error_not_a_guessed_zero(self, pipeline):
        """契约变了就报出来，不许拿 len(items) 之类去猜。"""
        class _NoCount:
            def list_object_types(self, oid):
                return {"status": "ok", "object_types": [1, 2, 3]}

            def list_link_types(self, oid):
                return {"status": "ok", "count": 1}

            def list_action_types(self, oid):
                return {"status": "ok", "count": 1}

            def list_process_types(self, oid):
                return {"status": "ok", "count": 1}

            def list_rule_types(self, oid):
                return {"status": "ok", "count": 1}

        counts, errors = _call_count_with(pipeline, _NoCount(), "ont-1")
        assert "object_types" not in counts
        assert counts["link_types"] == 1
        assert any("count" in e and "object_types" in e for e in errors), errors

    def test_non_dict_return_is_an_error(self, pipeline):
        class _List:
            def list_object_types(self, oid):
                return [{"type_id": "t1"}]

            def list_link_types(self, oid):
                return {"status": "ok", "count": 0}

            def list_action_types(self, oid):
                return {"status": "ok", "count": 0}

            def list_process_types(self, oid):
                return {"status": "ok", "count": 0}

            def list_rule_types(self, oid):
                return {"status": "ok", "count": 0}

        counts, errors = _call_count_with(pipeline, _List(), "ont-1")
        assert "object_types" not in counts
        assert any("非 dict" in e for e in errors), errors

    def test_empty_ontology_id_is_an_error_not_empty_counts(self, pipeline):
        counts, errors = pipeline._count_ontology_types("")
        assert counts == {}
        assert errors and "ontology_id" in errors[0]

    def test_list_usl_ontologies_surfaces_warnings(self, pipeline, monkeypatch):
        """悬空 domain_code 与类型统计失败都要出现在响应的 warnings 里。"""

        class _OntSvc:
            def list_ontologies(self, workspace_id=None):
                return {"status": "ok", "ontologies": [
                    {"ontology_id": "o1", "name": "USL__sanguo",
                     "domain_code": "sanguo", "workspace_id": "ws-1"},
                    {"ontology_id": "o2", "name": "USL__ghost",
                     "domain_code": "ghost", "workspace_id": "ws-1"},
                ]}

            def list_object_types(self, oid):
                return {"status": "ok", "object_types": [{"type_id": "t"}], "count": 1}

        class _UslSvc:
            def list_domains(self, page=1, page_size=500):
                return {"status": "ok", "items": [
                    {"code": "sanguo", "display_name": "三国"},
                ]}

        # OntologyService 必须打在**定义模块**上，不能打在 odap.biz.core.ontology.public
        # 门面上：该门面用 PEP 562 惰性 __getattr__ 解析符号，monkeypatch.setattr 撤销
        # 时会把原值 setattr 回门面，于是在门面 __dict__ 里留下一个永久真实属性，此后
        # 任何对定义模块的 patch 都失效（曾让 test_domain_resolution_chain 随机红）。
        # UslManagerService 走的是 services/__init__ 的 eager 再导出（真实 __dict__ 项），
        # monkeypatch 撤销后能正确还原，因此仍打在包属性上——那才是被测代码的导入点。
        monkeypatch.setattr(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            _OntSvc, raising=True,
        )
        monkeypatch.setattr(
            "odap.biz.semantic_admin.usl_manager.services.UslManagerService",
            _UslSvc, raising=True,
        )

        res = pipeline.list_usl_ontologies()
        assert res["status"] == "ok"
        assert [i["ontology_id"] for i in res["items"]] == ["o1", "o2"]

        o1 = res["items"][0]
        assert o1["type_counts"]["object_types"] == 1
        assert o1["type_count_errors"], "4 类方法缺失却没报错"

        o2 = res["items"][1]
        assert o2["domain_display_name"] == ""
        assert o2["display_label"] == "ghost"

        joined = " ".join(res["warnings"])
        assert "悬空引用" in joined and "ghost" in joined
        assert "link_types" in joined


def _call_count_with(pipeline, stub_svc, ontology_id):
    """把 stub 注入 _count_ontology_types 的 OntologyService 导入点并调用真方法体。

    打在定义模块而非 public 门面上，理由同 test_list_usl_ontologies_surfaces_warnings。
    """
    from unittest.mock import patch

    with patch(
        "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
        stub_svc.__class__,
    ):
        return pipeline._count_ontology_types(ontology_id)


# ──────────────────────────────────────────────────────────────────────
# 8. API 边界：Pydantic 默认 extra="ignore"，未声明字段会被静默丢弃
# ──────────────────────────────────────────────────────────────────────
class TestResponseSchemaKeepsCollectionFields:
    def test_run_response_preserves_stats_and_warnings(
        self, pipeline, ingest_storage,
    ):
        """服务层报出的归集统计/告警必须能穿过 response_model 到前端。"""
        from odap.biz.semantic_admin.semantic_asset_pipeline.api.schemas import (
            PipelineRunResponse,
        )

        doc = _make_doc("doc-ok", entities=[_entity(name="边界实体")])
        ingest_storage.save_ontology_document(doc)
        # 声明 2 个文档但只存 1 个 → 必然产生 warning
        _seed_record(ingest_storage, "rec-boundary", ["doc-ok", "doc-missing"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-boundary"},
            run_id="run-boundary", ontology_id="ont-test", source_kind="structured",
        )
        assert out["warnings"], "本用例应当产生告警"

        result = {
            "status": "ok",
            "pipeline_run_id": "run-boundary",
            "source_kind": "structured",
            "source_type": "manual",
            "candidate_count": len(out["records"]),
            "candidates": out["records"],
            "ingest": {"status": "ok", "record_id": "rec-boundary"},
            "collection_stats": out["stats"],
            "collection_warnings": out["warnings"],
        }
        resp = PipelineRunResponse(**result)

        assert resp.collection_stats == out["stats"]
        assert resp.collection_warnings == out["warnings"]
        assert resp.candidate_count == len(out["records"]) > 0
        # 序列化后仍在（前端拿到的是 JSON）
        dumped = resp.model_dump()
        assert dumped["collection_warnings"] == out["warnings"]
        assert dumped["collection_stats"]["by_semantic_type"]["对象类型"] == 1

    def test_response_model_declares_the_fields(self):
        """回归闸：字段被删掉时 extra=ignore 会让上面的断言静默通过空值。"""
        from odap.biz.semantic_admin.semantic_asset_pipeline.api.schemas import (
            PipelineRunResponse,
        )

        fields = PipelineRunResponse.model_fields
        assert "collection_stats" in fields, sorted(fields)
        assert "collection_warnings" in fields, sorted(fields)


# ──────────────────────────────────────────────────────────────────────
# 7. 源码级回归闸：探测式降级不许回来
# ──────────────────────────────────────────────────────────────────────
class TestNoProbeDegradationInSource:
    def test_no_hasattr_or_default_getattr_probes(self):
        """规则 14：hasattr / getattr(x, name, default) 探测会把改名伪装成"没数据"。

        这条闸盯的是具体失效形态，不是禁一切 getattr：
        - `hasattr(svc, ...)` 三元式 —— 探测失败静默走空分支；
        - `getattr(svc, name, None)` —— 同上；
        文档字段访问已改成直接属性访问，故全文不应再有带默认值的 getattr。
        """
        assert _PIPELINE_SERVICE_PY.is_file(), (
            f"审计目标不存在（布局已变更？）: {_PIPELINE_SERVICE_PY}"
        )
        tree = ast.parse(_PIPELINE_SERVICE_PY.read_text(encoding="utf-8"))

        offenders: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                fn = node.func.id
                if fn == "hasattr":
                    offenders.append(f"L{node.lineno}: hasattr(...) 探测")
                elif fn == "getattr" and len(node.args) >= 3:
                    offenders.append(
                        f"L{node.lineno}: getattr(..., default) 探测式降级"
                    )
        assert not offenders, (
            "pipeline_service.py 出现探测式降级（规则 14）:\n  "
            + "\n  ".join(offenders)
        )

    def test_count_ontology_types_declares_tuple_return(self):
        """返回值必须带 errors 通道，否则失败无处可去，只能塌成 0。"""
        src = _PIPELINE_SERVICE_PY.read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "_count_ontology_types"),
            None,
        )
        assert fn is not None, "_count_ontology_types 已被删除或改名"
        assert ast.unparse(fn.returns) == "Tuple[Dict[str, int], List[str]]", (
            f"返回类型退化为 {ast.unparse(fn.returns)}，errors 通道消失"
        )
        # 方法体里不许再出现「except: 计数写 0」这种塌缩
        body_src = ast.unparse(fn)
        assert "counts[kind] = 0" not in body_src, (
            "失败又被塌成 counts[kind] = 0"
        )


# ──────────────────────────────────────────────────────────────────────
# 8. 候选领域归属（断链 2）：domain_id 必须携带 ADR-079 §7 的 domain_code
# ──────────────────────────────────────────────────────────────────────
class TestCandidateDomainAttribution:
    """规则 14 第 4 条：领域归属只能来自本体真实 domain_code，不许按命名猜。

    历史缺陷：候选恒无 domain_id → 审核台无法按领域过滤 → 业务人员看不到
    自己领域的待审语义。本组用例走真实 `_collect_structured_candidates`
    函数体（规则 14 第 6 条），并回读真实 candidate_store 验证「报了 N 条」
    ==「库里真有 N 条且带领域」。
    """

    def test_structured_candidates_carry_domain_id(self, pipeline, ingest_storage):
        doc = _make_doc("doc-dom", entities=[_entity()], relations=[_relation()])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-dom", ["doc-dom"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-dom"},
            run_id="run-dom", ontology_id="ont-test",
            source_kind="structured", domain_code="MILITARY",
        )

        assert out["status"] == "ok", out
        assert out["records"], "应当归集出候选"
        assert all(r["domain_id"] == "MILITARY" for r in out["records"]), out["records"]

    def test_domain_id_persisted_to_candidate_store(self, pipeline, ingest_storage):
        doc = _make_doc("doc-dom2", entities=[_entity(name="蓝方守备连")])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-dom2", ["doc-dom2"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-dom2"},
            run_id="run-dom2", ontology_id="ont-test",
            source_kind="structured", domain_code="MILITARY",
        )
        assert out["status"] == "ok", out

        persisted = _persisted(pipeline, "run-dom2")
        assert persisted, "候选应已落库"
        assert all(p["domain_id"] == "MILITARY" for p in persisted), persisted

    def test_default_domain_code_is_empty_not_guessed(self, pipeline, ingest_storage):
        """未显式传 domain_code → domain_id 落空串，绝不从 ontology_id 反推。"""
        doc = _make_doc("doc-nodom", entities=[_entity(name="无领域实体")])
        ingest_storage.save_ontology_document(doc)
        _seed_record(ingest_storage, "rec-nodom", ["doc-nodom"])

        out = pipeline._collect_structured_candidates(
            {"status": "ok", "record_id": "rec-nodom"},
            run_id="run-nodom", ontology_id="ont-test", source_kind="structured",
        )
        assert out["status"] == "ok", out
        assert out["records"]
        assert all(r["domain_id"] == "" for r in out["records"]), out["records"]


class TestResolveDomainCode:
    """`_resolve_domain_code` 真实函数体：读本体 domain_code，读不到落空串。

    规则 14：读取失败记 warning 并返回空串（第 3 条），绝不猜测性反推
    （第 4 条）。这里 patch 的是 OntologyService（外部依赖边界），被测的
    `_resolve_domain_code` 函数体照常执行 —— 不是 patch 被测函数本身（第 6 条）。
    """

    @staticmethod
    def _patch_service(return_value):
        from unittest.mock import MagicMock, patch

        fake = MagicMock()
        fake.get_ontology.return_value = return_value
        # _resolve_domain_code 内部 `from ...public import OntologyService`，
        # patch 门面属性即可拦截（PEP 562 __getattr__ 会先解析出真类再被覆盖）。
        return patch(
            "odap.biz.core.ontology.public.OntologyService",
            return_value=fake,
        )

    def test_reads_domain_code_from_ontology(self, pipeline):
        with self._patch_service({"ontology_id": "o1", "domain_code": "FINANCE"}):
            assert pipeline._resolve_domain_code("o1") == "FINANCE"

    def test_missing_ontology_id_returns_empty(self, pipeline):
        assert pipeline._resolve_domain_code(None) == ""
        assert pipeline._resolve_domain_code("") == ""

    def test_error_status_returns_empty(self, pipeline):
        with self._patch_service({"status": "error", "message": "not found"}):
            assert pipeline._resolve_domain_code("o404") == ""

    def test_missing_domain_code_key_returns_empty(self, pipeline):
        with self._patch_service({"ontology_id": "o2"}):
            assert pipeline._resolve_domain_code("o2") == ""


class TestUnstructuredCandidateDomainAttribution:
    """断链 2 在非结构化路径的对称覆盖：`_collect_candidates` 也必须带 domain_id。

    走真实函数体（规则 14 第 6 条）；candidate_storage 是 fixture 注入的
    tmp_path 真库，故可回读验证「报了 N 条」==「库里真有 N 条且带领域」。
    """

    def test_unstructured_candidates_carry_domain_id(self, pipeline):
        merged = {
            "object_types": [
                {"name": "客户", "description": "购买方", "confidence": 0.9},
            ],
            "link_types": [{"name": "下单", "confidence": 0.8}],
        }
        records = pipeline._collect_candidates(
            merged, run_id="run-u1", template_ref="tpl-1",
            ontology_id="ont-fin", source_kind="unstructured",
            domain_code="FINANCE",
        )
        assert records, "应当归集出候选"
        assert all(r["domain_id"] == "FINANCE" for r in records), records

        persisted = _persisted(pipeline, "run-u1")
        assert len(persisted) == len(records)
        assert all(p["domain_id"] == "FINANCE" for p in persisted), persisted

    def test_unstructured_default_domain_code_is_empty(self, pipeline):
        merged = {"object_types": [{"name": "无领域对象"}]}
        records = pipeline._collect_candidates(
            merged, run_id="run-u2", template_ref="tpl-2",
            ontology_id="ont-x", source_kind="unstructured",
        )
        assert records and all(r["domain_id"] == "" for r in records), records


# ──────────────────────────────────────────────────────────────────────
# 9. 事件源候选归集（ADR-082 §1）
# ──────────────────────────────────────────────────────────────────────
def _extraction(**overrides):
    """构造门面透传的 extraction dict（键对齐 LLM 抽取契约）。"""
    base: Dict[str, Any] = {
        "entities": [{
            "entity_id": "e1", "entity_type": "Unit", "name": "红方装甲营",
            "basic_properties": {"description": "红方主力装甲部队", "side": "Red"},
            "statistical_properties": {"personnel": 420},
        }],
        "relations": [{
            "relation_id": "r1", "relation_type": "隶属于",
            "source_entity": "红方装甲营", "target_entity": "红方第1师",
        }],
        "events": [{
            "event_id": "ev1", "event_type": "装甲推进",
            "description": "红方装甲营向蓝方阵地推进",
            "participants": ["红方装甲营", "蓝方守备连"], "location": "北线",
        }],
        "actions": [],
        "confidence": 0.8,
    }
    base.update(overrides)
    return base


class TestEventCandidateCollection:
    def test_event_extraction_maps_to_usl_semantic_types(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-1", "extraction": _extraction()},
            run_id="run-ev", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok", out
        grouped = _by_type(out["records"])
        assert grouped["对象类型"][0]["canonical"] == "红方装甲营"
        assert grouped["关系类型"][0]["canonical"] == "隶属于"
        assert grouped["过程类型"][0]["canonical"] == "装甲推进"
        # 事件源是 LLM 推断，置信度取抽取置信度、origin=llm（区别于结构化的 1.0/structured）
        obj = grouped["对象类型"][0]
        assert obj["origin"] == "llm"
        assert obj["confidence"] == 0.8
        assert obj["definition"] == "红方主力装甲部队"
        assert obj["provenance"]["event_id"] == "evt-1"
        assert obj["provenance"]["entity_type"] == "Unit"
        # 属性槽位（basic/statistical）归为「属性」，capabilities/constraints 不入候选
        attrs = {a["canonical"] for a in grouped["属性"]}
        assert {"description", "side", "personnel"} <= attrs
        assert grouped["关系类型"][0]["source_text"] == (
            "红方装甲营 --[隶属于]--> 红方第1师"
        )
        assert grouped["过程类型"][0]["provenance"]["participants"] == [
            "红方装甲营", "蓝方守备连",
        ]

    def test_actions_empty_produces_no_action_candidates(self, pipeline):
        """perception 恒返回 actions=[]，必须如实产出 0 条动作候选，不得捏造。"""
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-2", "extraction": _extraction()},
            run_id="run-ev2", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok"
        assert "动作类型" not in _by_type(out["records"])

    def test_event_candidates_are_persisted(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-3", "extraction": _extraction()},
            run_id="run-ev3", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok"
        assert len(_persisted(pipeline, "run-ev3")) == len(out["records"]) > 0

    def test_missing_extraction_key_is_explicit_error(self, pipeline):
        """门面若没透传 extraction（契约破裂），必须显式报错而非静默 0 候选。"""
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-4"},
            run_id="run-ev4", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "error", out
        assert "extraction" in out["message"]

    def test_empty_extraction_is_ok_with_warning(self, pipeline):
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-5",
             "extraction": _extraction(entities=[], relations=[], events=[])},
            run_id="run-ev5", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "ok", out
        assert out["records"] == []
        assert out["warnings"], "空抽取应给出告警而非静默成功"

    def test_persistence_failure_is_error_not_false_ok(self, pipeline, monkeypatch):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        out = pipeline._collect_event_candidates(
            {"status": "ok", "event_id": "evt-6", "extraction": _extraction()},
            run_id="run-ev6", ontology_id=None, source_kind="event",
        )
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert _persisted(pipeline, "run-ev6") == []


# ──────────────────────────────────────────────────────────────────────
# 10. run() 事件源分流（ADR-082 §1/§3）
# ──────────────────────────────────────────────────────────────────────
class TestRunStructuredEventBranch:
    async def test_webhook_routes_to_event_collector(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "event_id": "evt-run", "routed_to": "PerceptionHub",
                    "extraction": _extraction(),
                }

        pipeline._ingest_facade = _Facade()
        # ontology_id=None 保持 hermetic：_resolve_domain_code 直接返回空串，
        # 不触发 OntologyService 构造（避免连 Neo4j）。
        res = await pipeline.run(
            source_type="webhook", payload={"payload": {"k": "v"}},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "ok", res
        assert res["candidate_count"] == len(res["candidates"]) > 0
        grouped = _by_type(res["candidates"])
        assert grouped["对象类型"][0]["canonical"] == "红方装甲营"
        # 事件候选 origin=llm（区别于结构化 1.0/structured）
        assert grouped["对象类型"][0]["origin"] == "llm"
        assert _persisted(pipeline, res["pipeline_run_id"])

    async def test_event_missing_extraction_bubbles_up(self, pipeline):
        class _Facade:
            async def ingest(self, source_type, **kwargs):
                return {
                    "status": "ok", "source_type": source_type,
                    "event_id": "evt-noext", "routed_to": "PerceptionHub",
                }

        pipeline._ingest_facade = _Facade()
        res = await pipeline.run(
            source_type="webhook", payload={"payload": {}},
            scenario_id="sc-test", workspace_id="ws-test",
        )
        assert res["status"] == "error", res
        assert "未能归集业务语义候选" in res["message"]
        assert res["ingest"]["event_id"] == "evt-noext"


# ──────────────────────────────────────────────────────────────────────
# 11. BI 指标候选归集（ADR-082 §2）
# ──────────────────────────────────────────────────────────────────────
def _indicator(**overrides):
    base: Dict[str, Any] = {
        "indicator_id": "ind-1",
        "name": "gmv_total",
        "display_name": "成交总额",
        "description": "统计周期内全部成交金额",
        "llm_description": "",
        "related_objects": ["订单"],
        "related_processes": ["下单"],
        "related_rules": ["退款规则"],
        "indicator_type": "metric",
        "calculation_formula": "SUM(order.amount)",
        "unit": "元",
        "ontology_id": "ont-test",
        "version_id": "v1",
    }
    base.update(overrides)
    return base


class TestIndicatorCandidateCollection:
    def test_indicator_maps_to_attribute_candidate(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind", ontology_id="ont-test",
            domain_code="FINANCE", version_id="v1",
        )
        assert out["status"] == "ok", out
        rec = out["records"][0]
        assert rec["semantic_type"] == "属性"
        assert rec["canonical"] == "成交总额"
        assert rec["definition"] == "统计周期内全部成交金额"
        assert rec["domain_id"] == "FINANCE"
        assert rec["confidence"] == 1.0
        assert rec["origin"] == "structured"
        assert rec["source_text"] == "SUM(order.amount)"
        prov = rec["provenance"]
        assert prov["attribute_of"] == "订单"
        assert prov["indicator_id"] == "ind-1"
        assert prov["indicator_type"] == "metric"
        assert prov["unit"] == "元"
        assert prov["version_id"] == "v1"

    def test_empty_related_objects_yields_empty_attribute_of_not_crash(self, pipeline):
        """related_objects 为空时 attribute_of 落空串，不得 IndexError（ADR-082 §2）。"""
        out = pipeline._collect_indicator_candidates(
            [_indicator(related_objects=[])], run_id="run-ind2", ontology_id="ont-test",
        )
        assert out["status"] == "ok", out
        assert out["records"][0]["provenance"]["attribute_of"] == ""

    def test_related_objects_not_emitted_as_separate_candidates(self, pipeline):
        """指标只产 1 条属性候选；related_objects/processes/rules 不另发（避免循环归类）。"""
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind3", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert len(out["records"]) == 1
        canonicals = {r["canonical"] for r in out["records"]}
        assert canonicals == {"成交总额"}
        assert "订单" not in canonicals and "下单" not in canonicals

    def test_name_fallback_when_no_display_name(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(display_name="", name="gmv_total")],
            run_id="run-ind4", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert out["records"][0]["canonical"] == "gmv_total"

    def test_definition_falls_back_to_llm_description(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(description="", llm_description="LLM 生成的口径")],
            run_id="run-ind5", ontology_id="ont-test",
        )
        assert out["records"][0]["definition"] == "LLM 生成的口径"

    def test_empty_indicator_list_is_ok_with_warning(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [], run_id="run-ind6", ontology_id="ont-test",
        )
        assert out["status"] == "ok", out
        assert out["records"] == []
        assert out["warnings"], "空指标列表应给出告警"

    def test_indicators_are_persisted(self, pipeline):
        out = pipeline._collect_indicator_candidates(
            [_indicator(), _indicator(indicator_id="ind-2", display_name="客单价",
                                      name="aov", related_objects=["订单"])],
            run_id="run-ind7", ontology_id="ont-test",
        )
        assert out["status"] == "ok"
        assert len(_persisted(pipeline, "run-ind7")) == len(out["records"]) == 2

    def test_persistence_failure_is_error_not_false_ok(self, pipeline, monkeypatch):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        out = pipeline._collect_indicator_candidates(
            [_indicator()], run_id="run-ind8", ontology_id="ont-test",
        )
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert _persisted(pipeline, "run-ind8") == []


# ──────────────────────────────────────────────────────────────────────
# 12. run() BI 指标分派（ADR-082 §2/§3）
# ──────────────────────────────────────────────────────────────────────
class TestRunIndicatorDispatch:
    async def test_business_indicators_routes_to_indicator_collector(self, pipeline):
        from unittest.mock import patch

        class _BizSvc:
            def list_indicators(self, ontology_id=None, version_id=None):
                assert ontology_id == "ont-test"
                return [_indicator()]

        class _FakeOntSvc:
            def get_ontology(self, oid):
                return {"ontology_id": oid, "domain_code": "FINANCE"}

        pipeline._business_service = _BizSvc()
        # patch 定义模块（非 public 门面）：门面 PEP 562 __getattr__ 会被 monkeypatch
        # 撤销时污染成永久真实属性（见本文件 test_list_usl_ontologies 注释）。
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            _FakeOntSvc,
        ):
            res = await pipeline.run(
                source_type="business_indicators", ontology_id="ont-test",
                payload={"version_id": "v1"},
            )
        assert res["status"] == "ok", res
        assert res["source_kind"] == "indicator"
        assert res["candidate_count"] == 1
        rec = res["candidates"][0]
        assert rec["semantic_type"] == "属性"
        assert rec["canonical"] == "成交总额"
        assert rec["domain_id"] == "FINANCE"
        assert _persisted(pipeline, res["pipeline_run_id"])

    async def test_missing_ontology_id_is_explicit_error(self, pipeline):
        res = await pipeline.run(
            source_type="business_indicators", ontology_id=None, payload={},
        )
        assert res["status"] == "error", res
        assert "ontology_id" in res["message"]

    async def test_list_indicators_exception_is_explicit_error(self, pipeline):
        class _BoomSvc:
            def list_indicators(self, ontology_id=None, version_id=None):
                raise RuntimeError("business.db locked")

        pipeline._business_service = _BoomSvc()
        res = await pipeline.run(
            source_type="business_indicators", ontology_id="ont-test", payload={},
        )
        assert res["status"] == "error", res
        assert "business.db locked" in res["message"]

    async def test_unknown_source_type_is_error(self, pipeline):
        res = await pipeline.run(source_type="not_a_real_source", payload={})
        assert res["status"] == "error", res
        assert "未知数据源类型" in res["message"]


# ──────────────────────────────────────────────────────────────────────
# 13. options() 暴露 indicator 源（ADR-082 §6）
# ──────────────────────────────────────────────────────────────────────
class TestOptionsExposeIndicatorSource:
    def test_source_types_include_indicator_group(self, pipeline, monkeypatch):
        # options() 会构造 TemplateEngine / OntologyService / UslManagerService 等
        # 重依赖；这里只验证 source_types 结构，故把三段外部构造打成轻量桩，
        # 被测的 options() 函数体（含 source_types 组装）照常执行（规则 14 要求 6）。
        monkeypatch.setattr(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            type("_S", (), {"list_ontologies": lambda self, workspace_id=None: {
                "status": "ok", "ontologies": []}}),
            raising=True,
        )
        monkeypatch.setattr(
            "odap.biz.semantic_admin.usl_manager.services.UslManagerService",
            type("_U", (), {"list_domains": lambda self, page=1, page_size=500: {
                "status": "ok", "items": []}}),
            raising=True,
        )

        res = pipeline.options()
        assert res["status"] == "ok"
        st = res["source_types"]
        assert st["indicator"] == ["business_indicators"]
        # 既有两组不回归
        assert "webhook" in st["structured"]
        assert "natural_language" in st["unstructured"]


class TestPersistRecordsHelper:
    """_persist_records 直测：空→None / 成功→None / 失败→显式 error dict。

    走真实函数体（规则 14 第 6 条）—— 仅在存储边界 patch
    bulk_insert_candidates，绝不 patch 被测方法 _persist_records 本身。
    """

    def test_empty_records_returns_none_without_touching_storage(
        self, pipeline, monkeypatch,
    ):
        def _boom(_records):
            raise AssertionError("空记录不应触发落库")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        assert pipeline._persist_records([], "结构化") is None

    def test_success_returns_none_and_writes_records(self, pipeline, monkeypatch):
        seen = {}

        def _capture(records):
            seen["records"] = records

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _capture, raising=True,
        )
        records = [{"canonical": "c1"}, {"canonical": "c2"}]
        assert pipeline._persist_records(records, "事件") is None
        assert seen["records"] is records

    def test_failure_returns_explicit_error_with_label_and_count(
        self, pipeline, monkeypatch,
    ):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        records = [{"canonical": "c1"}, {"canonical": "c2"}, {"canonical": "c3"}]
        out = pipeline._persist_records(records, "BI 指标")
        assert out is not None
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert "BI 指标" in out["message"]
        assert "3 条未持久化" in out["message"]
