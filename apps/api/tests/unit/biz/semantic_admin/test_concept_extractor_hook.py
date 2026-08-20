"""Semantic Admin — ConceptExtractor.run_l1_l2_hook 单元测试。

版块清理（2026-08-07）：007 提供 ConceptExtractor.run_l1_l2_hook() 接口供 006
ExtractService mode=schema_learning 调用，将 006 抽取结果转换为 USL SchemaCandidate
并写入 candidate_store。

测试覆盖：
  1. 基本转换：5 类 ODAP 类型（object_types/link_types/action_types/rule_types/process_types）→ USL candidate
  2. 通用 entities 回退路径（5 类为空时）
  3. semantic_type 推断（英文别名 / 直接命中 6 枚举 / 默认"对象类型"）
  4. 同义词/英文/置信度/定义字段提取（多键优先级）
  5. 跨类型去重（同一 canonical 跨多个 ODAP 类型列表只保留首次）
  6. 与 USL 术语去重（canonical 命中 / synonym 命中）
  7. 元数据补充（id / pipeline_run_id / workspace_id / origin / status / provenance）
  8. candidate_storage 注入：成功写入 + 异常时不阻断
  9. usl_storage 异常降级（跳过去重）
 10. 返回字段完整性（candidates/count/source/written/deduped_count/l1_tokens/l2_concepts）
 11. JSON 字符串同义词解析（逗号分隔 / JSON 数组）
 12. 边界：空 merged / 空 entities / 非法 item 类型
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.ol_pipeline.services.concept_extractor import (
    ConceptExtractor,
)
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cand_storage(tmp_path: Path) -> SQLiteCandidateStorage:
    """候选存储 tmp_path 真实 SQLite（AGENTS.md §C 测试规则）。"""
    return SQLiteCandidateStorage(db_path=str(tmp_path / "cands.db"))


@pytest.fixture
def usl_storage(tmp_path: Path) -> SQLiteUslStorage:
    """USL 术语存储 tmp_path 真实 SQLite。"""
    return SQLiteUslStorage(db_path=str(tmp_path / "usl.db"))


@pytest.fixture
def extractor_no_storage() -> ConceptExtractor:
    """无 storage 注入的 extractor（仅返回 candidates，不写 DB）。"""
    return ConceptExtractor()


@pytest.fixture
def extractor_with_storage(
    cand_storage: SQLiteCandidateStorage,
    usl_storage: SQLiteUslStorage,
) -> ConceptExtractor:
    """注入真实 storage 的 extractor。"""
    return ConceptExtractor(
        candidate_storage=cand_storage,
        usl_storage=usl_storage,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _odap_object_type(name: str, **kw: Any) -> Dict[str, Any]:
    """构造 006 ODAP object_type 项。"""
    d: Dict[str, Any] = dict(
        name=name,
        type="object",
        description=f"{name} 的定义",
        confidence=0.85,
        aliases=[f"{name}_别名"],
    )
    d.update(kw)
    return d


def _odap_link_type(name: str, **kw: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = dict(
        name=name,
        type="link",
        description=f"关系：{name}",
        confidence=0.78,
    )
    d.update(kw)
    return d


def _merged(**sections) -> Dict[str, Any]:
    """构建 006 ExtractService merged 结果。

    默认所有 6 个 section 都为空，由测试按需填入。
    """
    base: Dict[str, Any] = {
        "entities": [],
        "object_types": [],
        "link_types": [],
        "action_types": [],
        "rule_types": [],
        "process_types": [],
        "attribute_types": [],
        "conflicts": [],
    }
    base.update(sections)
    return base


# ======================================================================
# 组 1：基本转换
# ======================================================================


class TestBasicConversion:
    def test_object_types_extracted_to_usl_candidate(self, extractor_no_storage):
        merged = _merged(
            object_types=[_odap_object_type("客户"), _odap_object_type("订单")]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)

        assert result["source"] == "007_concept_extractor"
        assert result["count"] == 2
        assert result["l1_tokens"] == 2
        assert result["l2_concepts"] == 2
        assert result["written"] is False  # 无 storage 注入

        cands = result["candidates"]
        names = [c["canonical"] for c in cands]
        assert "客户" in names
        assert "订单" in names

        # semantic_type 应映射为 USL "对象类型"
        for c in cands:
            assert c["semantic_type"] == "对象类型"

    def test_link_types_mapped_to_relation_type(self, extractor_no_storage):
        merged = _merged(
            link_types=[_odap_link_type("购买"), _odap_link_type("拥有")]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)

        for c in result["candidates"]:
            assert c["semantic_type"] == "关系类型"
        assert result["count"] == 2

    def test_action_types_mapped_correctly(self, extractor_no_storage):
        merged = _merged(
            action_types=[{"name": "下单", "type": "action", "confidence": 0.9}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["semantic_type"] == "动作类型"

    def test_rule_types_mapped_correctly(self, extractor_no_storage):
        merged = _merged(
            rule_types=[{"name": "复购规则", "type": "rule", "confidence": 0.6}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["semantic_type"] == "规则类型"

    def test_process_types_mapped_correctly(self, extractor_no_storage):
        merged = _merged(
            process_types=[{"name": "支付流程", "type": "process", "confidence": 0.7}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["semantic_type"] == "过程类型"

    def test_attribute_types_mapped_to_attribute(self, extractor_no_storage):
        merged = _merged(
            attribute_types=[{"name": "价格", "type": "attribute", "confidence": 0.8}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["semantic_type"] == "属性"


# ======================================================================
# 组 2：通用 entities 回退
# ======================================================================


class TestEntitiesFallback:
    def test_entities_used_when_odap_types_empty(self, extractor_no_storage):
        merged = _merged(
            entities=[
                {"name": "通用实体1", "type": "对象类型", "description": "d1"},
                {"name": "通用实体2", "type": "关系类型", "description": "d2"},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)

        assert result["count"] == 2
        sem_types = {c["semantic_type"] for c in result["candidates"]}
        assert "对象类型" in sem_types
        assert "关系类型" in sem_types

    def test_entities_ignored_when_odap_types_present(self, extractor_no_storage):
        """当 ODAP 5 类有数据时，entities 应被忽略。"""
        merged = _merged(
            object_types=[_odap_object_type("ODAP实体")],
            entities=[{"name": "通用实体", "type": "对象类型"}],
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "ODAP实体"

    def test_entities_with_english_type_alias(self, extractor_no_storage):
        """entity.type='object' 应推断为"对象类型"。"""
        merged = _merged(
            entities=[{"name": "X", "type": "object"}, {"name": "Y", "type": "link"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        types = {c["canonical"]: c["semantic_type"] for c in result["candidates"]}
        assert types["X"] == "对象类型"
        assert types["Y"] == "关系类型"

    def test_entities_with_unknown_type_defaults_to_object(self, extractor_no_storage):
        merged = _merged(
            entities=[{"name": "Z", "type": "unknown_type"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["semantic_type"] == "对象类型"


# ======================================================================
# 组 3：字段提取（多键优先级）
# ======================================================================


class TestFieldExtraction:
    def test_canonical_uses_name_first(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "首选名", "canonical": "应被忽略", "term": "t"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["canonical"] == "首选名"

    def test_canonical_fallback_to_canonical_key(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"canonical": "用canonical字段"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["canonical"] == "用canonical字段"

    def test_canonical_fallback_to_term_or_label(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"term": "用term"},
                {"label": "用label"},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        names = [c["canonical"] for c in result["candidates"]]
        assert "用term" in names
        assert "用label" in names

    def test_item_without_name_skipped(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"description": "no name"},
                {"name": "有name"},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "有name"

    def test_synonyms_extracted_from_aliases(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": "X", "aliases": ["别名1", "别名2"]},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        syns = result["candidates"][0]["synonyms"]
        assert "别名1" in syns
        assert "别名2" in syns

    def test_synonyms_extracted_from_synonyms_key(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": "X", "synonyms": ["同义1", "同义2"]},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["synonyms"] == ["同义1", "同义2"]

    def test_synonyms_extracted_from_alt_names(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": "X", "alt_names": ["alt1", "alt2"]},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert "alt1" in result["candidates"][0]["synonyms"]

    def test_synonyms_comma_separated_string(self, extractor_no_storage):
        """synonyms 字段为逗号分隔字符串时应解析为 list。"""
        merged = _merged(
            object_types=[{"name": "X", "synonyms": "词1, 词2, 词3"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["synonyms"] == ["词1", "词2", "词3"]

    def test_synonyms_json_string_parsed(self, extractor_no_storage):
        """synonyms 字段为 JSON 数组字符串时应解析为 list。"""
        import json
        merged = _merged(
            object_types=[{"name": "X", "synonyms": json.dumps(["j1", "j2"])}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["synonyms"] == ["j1", "j2"]

    def test_en_extracted_from_multiple_keys(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": "X1", "en": "EnglishName1"},
                {"name": "X2", "en_name": "EnglishName2"},
                {"name": "X3", "english_name": "EnglishName3"},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        ens = {c["canonical"]: c["en"] for c in result["candidates"]}
        assert ens["X1"] == "EnglishName1"
        assert ens["X2"] == "EnglishName2"
        assert ens["X3"] == "EnglishName3"

    def test_confidence_default_0_7_when_missing(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X"}]  # 无 confidence
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["confidence"] == 0.7

    def test_confidence_uses_score_field(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X", "score": 0.92}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["confidence"] == 0.92

    def test_confidence_clamped_to_01(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": "X1", "confidence": 1.5},  # 超 1
                {"name": "X2", "confidence": -0.3},  # 负数
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        confs = {c["canonical"]: c["confidence"] for c in result["candidates"]}
        assert confs["X1"] == 1.0  # clamp
        assert confs["X2"] == 0.0  # clamp

    def test_definition_extracted_from_description(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X", "description": "这是定义"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["definition"] == "这是定义"

    def test_definition_extracted_from_definition_key(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X", "definition": "用 definition 字段"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["definition"] == "用 definition 字段"


# ======================================================================
# 组 4：跨类型去重
# ======================================================================


class TestCrossTypeDedup:
    def test_same_canonical_across_types_kept_once(self, extractor_no_storage):
        """同一 canonical 同时出现在 object_types 和 link_types 中，
        应只保留首次出现（object_types 优先）。"""
        merged = _merged(
            object_types=[{"name": "重复名", "type": "object"}],
            link_types=[{"name": "重复名", "type": "link"}],
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        # 应保留 object_types 的版本（语义类型为"对象类型"）
        assert result["candidates"][0]["semantic_type"] == "对象类型"

    def test_dedup_case_insensitive(self, extractor_no_storage):
        """canonical 去重应小写化（"客户" vs "客户" 完全相同；
        但英文 "Customer" vs "customer" 应去重为 1 项）。"""
        merged = _merged(
            object_types=[{"name": "Customer"}],
            link_types=[{"name": "customer"}],
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "Customer"


# ======================================================================
# 组 5：与 USL 术语去重
# ======================================================================


def _seed_usl_term(usl_storage, canonical: str, synonyms: List[str]) -> str:
    """辅助：先建 domain 再写 term，返回 domain_id。"""
    import uuid
    from datetime import datetime, timezone
    domain_id = f"dom-{uuid.uuid4().hex[:8]}"
    usl_storage.save_domain({
        "id": domain_id,
        "code": f"code-{domain_id}",
        "display_name": f"Test Domain {domain_id}",
        "description": "",
        "en_mapping": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    usl_storage.save_term({
        "id": f"term-{uuid.uuid4().hex[:12]}",
        "domain_id": domain_id,
        "canonical": canonical,
        "semantic_type": "对象类型",
        "synonyms": synonyms,
        "near_synonyms": [],
        "aliases": [],
        "stoplist_flag": False,
        "definition": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return domain_id


class TestUslDedup:
    def test_canonical_match_usl_term_skipped(self, usl_storage):
        """candidate.canonical 命中 USL 既有术语 → 跳过。"""
        # 先写入一个 USL 术语
        _seed_usl_term(usl_storage, "已存在术语", [])
        extractor = ConceptExtractor(usl_storage=usl_storage)

        merged = _merged(
            object_types=[
                {"name": "已存在术语"},  # 应被去重
                {"name": "新术语"},
            ]
        )
        result = extractor.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "新术语"
        assert result["deduped_count"] == 1
        assert result["l1_tokens"] == 2  # 输入共 2 个

    def test_synonym_match_usl_term_skipped(self, usl_storage):
        """candidate.synonyms 任一项命中 USL 既有术语 → 跳过。"""
        _seed_usl_term(usl_storage, "规范术语", ["别名A"])
        extractor = ConceptExtractor(usl_storage=usl_storage)

        merged = _merged(
            object_types=[
                # canonical 不命中，但 synonyms 命中
                {"name": "全新canonical", "synonyms": ["别名A"]},
                {"name": "保留项"},
            ]
        )
        result = extractor.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "保留项"

    def test_no_usl_storage_skips_dedup(self, extractor_no_storage):
        """usl_storage=None 时，跳过去重步骤（所有候选保留）。"""
        merged = _merged(
            object_types=[{"name": f"term_{i}"} for i in range(5)]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 5


# ======================================================================
# 组 6：元数据补充
# ======================================================================


class TestMetadataEnrichment:
    def test_id_generated_if_missing(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(merged)
        cand = result["candidates"][0]
        assert "id" in cand
        assert cand["id"]  # 非空
        # 应为合法 UUID
        import uuid
        uuid.UUID(cand["id"])  # 不抛异常即合法

    def test_id_always_generated_fresh(self, extractor_no_storage):
        """_convert_item_to_candidate 不从输入 item 继承 id（006 实体 id 与
        USL candidate id 是不同命名空间），故每次都生成新 UUID。"""
        merged = _merged(
            object_types=[{"name": "X", "id": "source-entity-id-123"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        cand_id = result["candidates"][0]["id"]
        # 应为新生成的 UUID（非输入 item 的 id）
        assert cand_id != "source-entity-id-123"
        import uuid
        uuid.UUID(cand_id)  # 验证是合法 UUID 格式

    def test_pipeline_run_id_set_when_run_id_provided(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(
            merged, run_id="run-abc-001"
        )
        assert result["candidates"][0]["pipeline_run_id"] == "run-abc-001"

    def test_workspace_id_default(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["workspace_id"] == "default"

    def test_workspace_id_custom(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(
            merged, workspace_id="ws-custom"
        )
        assert result["candidates"][0]["workspace_id"] == "ws-custom"

    def test_origin_always_llm(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X", "origin": "ignored"}])
        result = extractor_no_storage.run_l1_l2_hook(merged)
        # origin 应固定为 'llm'（hook 入口产出的都是 LLM 来源）
        assert result["candidates"][0]["origin"] == "llm"

    def test_status_default_draft(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["candidates"][0]["status"] == "DRAFT"

    def test_created_at_and_updated_at_set(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(merged)
        cand = result["candidates"][0]
        assert "created_at" in cand
        assert "updated_at" in cand
        assert cand["created_at"]  # 非空 ISO 字符串

    def test_provenance_contains_hook_source(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(
            merged, workspace_id="ws-1", ontology_id="ont-9"
        )
        prov = result["candidates"][0]["provenance"]
        assert prov["source"] == "007_concept_extractor.run_l1_l2_hook"
        assert prov["source_step"] == "l1_l2_hook"
        assert prov["hook_workspace_id"] == "ws-1"
        assert prov["hook_ontology_id"] == "ont-9"


# ======================================================================
# 组 7：candidate_storage 写入
# ======================================================================


class TestCandidateStorageWrite:
    def test_write_success_when_storage_injected(
        self, extractor_with_storage, cand_storage
    ):
        merged = _merged(
            object_types=[_odap_object_type("写入测试1"),
                          _odap_object_type("写入测试2")]
        )
        result = extractor_with_storage.run_l1_l2_hook(
            merged, run_id="run-write-001"
        )

        assert result["written"] is True
        assert result["count"] == 2

        # 验证已写入 candidate_store
        listed = cand_storage.list_candidates(pipeline_run_id="run-write-001")
        # list_candidates 返回 dict 形如 {"items": [...], "total": N}
        items = listed.get("items") or listed.get("data") or []
        total = listed.get("total", 0)
        assert total == 2
        assert len(items) == 2

    def test_write_failure_does_not_break_return(self, cand_storage):
        """candidate_storage.bulk_insert_candidates 抛异常时，written=False
        但 candidates 仍返回。"""
        # 用 MagicMock 模拟抛异常的 storage
        bad_storage = MagicMock()
        bad_storage.bulk_insert_candidates.side_effect = RuntimeError("DB 写入失败")
        extractor = ConceptExtractor(candidate_storage=bad_storage)

        merged = _merged(object_types=[_odap_object_type("X")])
        result = extractor.run_l1_l2_hook(merged, run_id="r1")

        assert result["written"] is False
        assert result["count"] == 1  # 仍返回 candidates
        assert len(result["candidates"]) == 1

    def test_no_write_when_no_candidates(self, extractor_with_storage):
        """空候选列表不应触发 storage 写入。"""
        merged = _merged()  # 全空
        result = extractor_with_storage.run_l1_l2_hook(merged)
        assert result["written"] is False
        assert result["count"] == 0
        assert result["candidates"] == []


# ======================================================================
# 组 8：usl_storage 异常降级
# ======================================================================


class TestUslStorageFailure:
    def test_usl_storage_exception_falls_back_to_no_dedup(self):
        """usl_storage.list_terms 抛异常时，应跳过去重（保留全部候选）。"""
        bad_usl = MagicMock()
        bad_usl.list_terms.side_effect = RuntimeError("USL DB 不可用")
        extractor = ConceptExtractor(usl_storage=bad_usl)

        merged = _merged(
            object_types=[{"name": f"term_{i}"} for i in range(3)]
        )
        result = extractor.run_l1_l2_hook(merged)

        # 异常被 catch，去重降级为空，3 个候选全保留
        assert result["count"] == 3

    def test_usl_storage_returns_unexpected_format(self):
        """usl_storage.list_terms 返回非预期格式（如 None）应降级为空列表。"""
        weird_usl = MagicMock()
        weird_usl.list_terms.return_value = None  # 非 tuple/list/dict
        extractor = ConceptExtractor(usl_storage=weird_usl)

        merged = _merged(
            object_types=[{"name": "X1"}, {"name": "X2"}]
        )
        result = extractor.run_l1_l2_hook(merged)
        assert result["count"] == 2  # 去重降级为空 → 全保留


# ======================================================================
# 组 9：返回字段完整性
# ======================================================================


class TestReturnShape:
    def test_return_has_all_required_fields(self, extractor_no_storage):
        merged = _merged(object_types=[{"name": "X"}])
        result = extractor_no_storage.run_l1_l2_hook(merged, run_id="r-1")

        required_keys = {
            "candidates", "count", "source", "written",
            "deduped_count", "l1_tokens", "l2_concepts",
        }
        assert required_keys.issubset(result.keys())

    def test_l1_tokens_equals_input_count(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X1"}, {"name": "X2"}, {"name": "X3"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["l1_tokens"] == 3

    def test_l2_concepts_equals_deduped_count(self, extractor_no_storage):
        merged = _merged(
            object_types=[{"name": "X1"}, {"name": "X2"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["l2_concepts"] == result["deduped_count"]
        assert result["l2_concepts"] == result["count"]

    def test_source_constant(self, extractor_no_storage):
        merged = _merged()
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["source"] == "007_concept_extractor"


# ======================================================================
# 组 10：边界场景
# ======================================================================


class TestEdgeCases:
    def test_empty_merged_returns_empty_candidates(self, extractor_no_storage):
        result = extractor_no_storage.run_l1_l2_hook(_merged())
        assert result["count"] == 0
        assert result["candidates"] == []
        assert result["l1_tokens"] == 0

    def test_merged_with_none_sections(self, extractor_no_storage):
        """sections 为 None 应被容错为空列表。"""
        merged = {
            "object_types": None,
            "link_types": None,
            "entities": None,
        }
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 0

    def test_merged_with_non_dict_items_skipped(self, extractor_no_storage):
        """列表项非 dict（如 str/int）应被跳过。"""
        merged = _merged(
            object_types=["not_a_dict", 123, {"name": "valid"}]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "valid"

    def test_merged_with_non_list_section_skipped(self, extractor_no_storage):
        """section 值非 list/tuple（如 dict/str）应被容错跳过。"""
        merged = _merged(
            object_types={"not": "a list"},
            link_types="also not a list",
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 0

    def test_item_with_empty_name_skipped(self, extractor_no_storage):
        merged = _merged(
            object_types=[
                {"name": ""},  # 空 name
                {"name": "   "},  # 空白 name
                {"name": "valid"},
            ]
        )
        result = extractor_no_storage.run_l1_l2_hook(merged)
        assert result["count"] == 1
        assert result["candidates"][0]["canonical"] == "valid"

    def test_extract_candidates_from_merged_internal(self, extractor_no_storage):
        """直接测试内部方法 _extract_candidates_from_merged。"""
        merged = _merged(
            object_types=[{"name": "X1"}, {"name": "X2"}],
            link_types=[{"name": "L1"}],
        )
        cands = extractor_no_storage._extract_candidates_from_merged(merged)
        assert len(cands) == 3
        types = {c["semantic_type"] for c in cands}
        assert types == {"对象类型", "关系类型"}

    def test_infer_usl_semantic_type_static_method(self):
        """测试 semantic_type 推断的别名映射。"""
        assert ConceptExtractor._infer_usl_semantic_type("对象类型") == "对象类型"
        assert ConceptExtractor._infer_usl_semantic_type("object") == "对象类型"
        assert ConceptExtractor._infer_usl_semantic_type("ObjectType") == "对象类型"
        assert ConceptExtractor._infer_usl_semantic_type("entity") == "对象类型"
        assert ConceptExtractor._infer_usl_semantic_type("link") == "关系类型"
        assert ConceptExtractor._infer_usl_semantic_type("relation") == "关系类型"
        assert ConceptExtractor._infer_usl_semantic_type("action") == "动作类型"
        assert ConceptExtractor._infer_usl_semantic_type("rule") == "规则类型"
        assert ConceptExtractor._infer_usl_semantic_type("process") == "过程类型"
        assert ConceptExtractor._infer_usl_semantic_type("attribute") == "属性"
        assert ConceptExtractor._infer_usl_semantic_type("property") == "属性"
        assert ConceptExtractor._infer_usl_semantic_type("") == "对象类型"
        assert ConceptExtractor._infer_usl_semantic_type("unknown") == "对象类型"


# ======================================================================
# 组 11：集成场景 — 完整 006 merged 输入
# ======================================================================


class TestIntegrationFullMerged:
    def test_realistic_006_merged_output(self, extractor_no_storage):
        """模拟 006 ExtractService 真实输出的 merged 结构。"""
        merged = _merged(
            object_types=[
                {"name": "客户", "type": "object",
                 "description": "购买商品或服务的人或组织",
                 "confidence": 0.92,
                 "aliases": ["顾客", "买家"]},
                {"name": "订单", "type": "object",
                 "description": "客户下达的购买请求",
                 "confidence": 0.88,
                 "en": "Order"},
            ],
            link_types=[
                {"name": "下达", "type": "link",
                 "description": "客户→订单的关系",
                 "confidence": 0.75},
            ],
            action_types=[
                {"name": "支付", "type": "action", "confidence": 0.81},
            ],
            rule_types=[
                {"name": "满减规则", "type": "rule", "confidence": 0.65},
            ],
            process_types=[
                {"name": "退款流程", "type": "process", "confidence": 0.72},
            ],
            conflicts=[],  # 006 输出的冲突列表，hook 应忽略
        )

        result = extractor_no_storage.run_l1_l2_hook(
            merged,
            workspace_id="ws-prod-001",
            ontology_id="ont-ecommerce",
            run_id="run-20260807-001",
        )

        assert result["count"] == 6
        assert result["l1_tokens"] == 6
        assert result["l2_concepts"] == 6
        assert result["written"] is False  # 无 storage

        # 验证所有候选都有完整元数据
        for cand in result["candidates"]:
            assert cand["workspace_id"] == "ws-prod-001"
            assert cand["ontology_id"] == "ont-ecommerce"
            assert cand["pipeline_run_id"] == "run-20260807-001"
            assert cand["origin"] == "llm"
            assert cand["status"] == "DRAFT"
            assert "id" in cand
            assert "created_at" in cand
            assert "provenance" in cand
            assert cand["provenance"]["hook_ontology_id"] == "ont-ecommerce"

        # semantic_type 分布正确
        sem_types = {c["canonical"]: c["semantic_type"] for c in result["candidates"]}
        assert sem_types["客户"] == "对象类型"
        assert sem_types["订单"] == "对象类型"
        assert sem_types["下达"] == "关系类型"
        assert sem_types["支付"] == "动作类型"
        assert sem_types["满减规则"] == "规则类型"
        assert sem_types["退款流程"] == "过程类型"

    def test_end_to_end_with_real_storage(
        self, extractor_with_storage, cand_storage
    ):
        """端到端：写入真实 candidate_store 并能查回。"""
        merged = _merged(
            object_types=[
                {"name": "产品", "type": "object",
                 "description": "可售卖的物品",
                 "confidence": 0.9,
                 "aliases": ["商品", "货物"]},
            ],
            link_types=[
                {"name": "包含", "type": "link", "confidence": 0.7},
            ],
        )
        result = extractor_with_storage.run_l1_l2_hook(
            merged, run_id="run-e2e-001"
        )

        assert result["written"] is True
        assert result["count"] == 2

        # 通过 storage 查回
        listed = cand_storage.list_candidates(pipeline_run_id="run-e2e-001")
        items = listed.get("items", [])
        total = listed.get("total", 0)
        assert total == 2
        assert len(items) == 2

        # 验证写入的数据可正确反序列化
        names = {item["canonical"] for item in items}
        assert "产品" in names
        assert "包含" in names

        # 产品的同义词应被持久化
        product = next(item for item in items if item["canonical"] == "产品")
        # synonyms 可能是 JSON 字符串或 list（取决于 storage 实现）
        syns = product.get("synonyms") or product.get("synonyms_json") or []
        if isinstance(syns, str):
            import json
            syns = json.loads(syns)
        assert "商品" in syns
        assert "货物" in syns
