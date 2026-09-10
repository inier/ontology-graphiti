"""span 级溯源 schema 冻结（prov-span-v1）的成功路径回归测试。

背景（圆桌结论·代码实证版 决策一）：图谱边/节点此前零溯源字段（裸边），
char_span 全库为零、chunk_id 在 normalization merge 阶段丢失、confidence 从不落图，
且这些属于"抽取当时没记就永远没有"的不可回填类别。schema 冻结错过窗口即永久丢数据。

本文件为"冻结契约 + 归一化写入 + merge 不丢"绑定成功路径断言，作为变异测试锚点：
一旦有人回退（GraphWriteStep 不再写溯源 / normalization merge 再次抹掉 chunk_id /
build_provenance_props 开始硬编码 confidence），这些测试必须变红。

规则（AGENTS.md）：Mock 外部服务（GraphManager），不 mock 被测逻辑本身；async 用 asyncio。
"""

import pytest
from unittest.mock import MagicMock, patch

from odap.biz.core.ontology.construction.provenance.provenance_schema import (
    SCHEMA_VERSION,
    PROVENANCE_FIELDS,
    FIELD_SCHEMA_VERSION,
    FIELD_SOURCE_DOC_IDS,
    FIELD_CHUNK_ID,
    FIELD_CHAR_SPAN,
    FIELD_CONFIDENCE,
    FIELD_EVIDENCE_TEXT,
    build_provenance_props,
    merge_provenance,
)


# ── 契约冻结本身 ──────────────────────────────────────────────────────

class TestSchemaFrozen:
    def test_frozen_field_names_are_stable(self):
        """冻结键名一旦定死不得漂移——这些字符串直接落图，改名即制造历史裸边。"""
        assert SCHEMA_VERSION == "prov-span-v1"
        assert FIELD_SOURCE_DOC_IDS == "source_doc_ids"
        assert FIELD_CHUNK_ID == "chunk_id"
        assert FIELD_CHAR_SPAN == "char_span"
        assert FIELD_CONFIDENCE == "confidence"
        assert FIELD_EVIDENCE_TEXT == "evidence_text"
        assert PROVENANCE_FIELDS == (
            "source_doc_ids", "chunk_id", "char_span", "confidence", "evidence_text",
        )

    def test_field_names_are_neo4j_safe(self):
        """冻结键必须满足 Neo4j property key 校验（^[a-zA-Z_][a-zA-Z0-9_]*$）。"""
        import re
        for key in PROVENANCE_FIELDS + (FIELD_SCHEMA_VERSION,):
            assert re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key), key


# ── 归一化写入 ────────────────────────────────────────────────────────

class TestBuildProvenanceProps:
    def test_version_stamp_always_present(self):
        """即便 record 无任何溯源信息，也盖版本戳（区分冻结时代数据 vs 历史裸边）。"""
        props = build_provenance_props({"id": "e1", "name": "Alice"})
        assert props[FIELD_SCHEMA_VERSION] == SCHEMA_VERSION
        # 无真值的冻结字段不写（不写空占位、不猜测补全 —— 规则 14）
        for key in PROVENANCE_FIELDS:
            assert key not in props

    def test_normalizes_aliases_and_unions_doc_ids(self):
        record = {
            "source_doc_id": "doc_A",              # 顶层单值别名
            "properties": {
                "doc_id": "doc_B",                 # properties 层别名 → 应并入
                "chunk": "chunk_7",
                "score": 0.83,
                "char_span": "12:40",
                "evidence": "Alice 负责北斗系统",
            },
        }
        props = build_provenance_props(record)
        assert props[FIELD_SOURCE_DOC_IDS] == ["doc_A", "doc_B"]
        assert props[FIELD_CHUNK_ID] == "chunk_7"
        assert props[FIELD_CONFIDENCE] == 0.83
        assert props[FIELD_CHAR_SPAN] == "12:40"
        assert props[FIELD_EVIDENCE_TEXT] == "Alice 负责北斗系统"

    def test_char_span_parses_list_and_dict(self):
        assert build_provenance_props({"char_span": [3, 9]})[FIELD_CHAR_SPAN] == "3:9"
        assert build_provenance_props({"offsets": {"start": 5, "end": 11}})[FIELD_CHAR_SPAN] == "5:11"

    def test_confidence_out_of_range_or_invalid_is_dropped(self):
        """confidence 越界/非法一律不写，绝不用硬编码默认值兜底（规则 14）。"""
        assert FIELD_CONFIDENCE not in build_provenance_props({"confidence": 1.5})
        assert FIELD_CONFIDENCE not in build_provenance_props({"confidence": -0.2})
        assert FIELD_CONFIDENCE not in build_provenance_props({"confidence": "high"})
        # 合法边界值保留
        assert build_provenance_props({"confidence": 0})[FIELD_CONFIDENCE] == 0.0
        assert build_provenance_props({"confidence": 1})[FIELD_CONFIDENCE] == 1.0

    def test_empty_and_none_values_not_written(self):
        props = build_provenance_props({
            "source_doc_ids": [], "chunk_id": "", "confidence": None, "evidence_text": "   ",
        })
        assert FIELD_SOURCE_DOC_IDS not in props
        assert FIELD_CHUNK_ID not in props
        assert FIELD_CONFIDENCE not in props
        assert FIELD_EVIDENCE_TEXT not in props

    def test_non_dict_record_only_version_stamp(self):
        assert build_provenance_props(None) == {FIELD_SCHEMA_VERSION: SCHEMA_VERSION}


class TestMergeProvenance:
    def test_union_doc_ids_and_keep_scalars(self):
        primary = {"name": "Alice", "properties": {"source_doc_id": "doc_A", "chunk_id": "c1"}}
        other = {"name": "Alice", "properties": {"source_doc_id": "doc_B", "confidence": 0.7}}
        merged = merge_provenance(primary, other)
        assert merged[FIELD_SOURCE_DOC_IDS] == ["doc_A", "doc_B"]
        assert merged[FIELD_CHUNK_ID] == "c1"          # primary 优先，未被抹掉
        assert merged[FIELD_CONFIDENCE] == 0.7         # primary 缺失 → 回退 other
        assert merged[FIELD_SCHEMA_VERSION] == SCHEMA_VERSION


# ── GraphWriteStep 溯源落图成功路径 ───────────────────────────────────

class TestGraphWriteProvenanceLanding:
    @pytest.mark.asyncio
    async def test_node_and_edge_carry_frozen_provenance(self):
        from odap.biz.core.ontology.construction.pipeline.services.step_handlers.graph_write import (
            GraphWriteStep,
        )

        fake_gm = MagicMock()
        fake_gm.add_entity = MagicMock(return_value=True)
        fake_gm.add_relationship = MagicMock(return_value=True)

        entities = [{
            "id": "e1", "entity_type": "Person", "name": "Alice",
            "source_doc_id": "doc_A",
            "properties": {"chunk_id": "c1", "confidence": 0.91},
        }]
        relations = [{
            "id": "r1", "relation_type": "knows",
            "source_entity_id": "e1", "target_entity_id": "e2",
            "properties": {"source_doc_ids": ["doc_A", "doc_C"], "evidence_text": "Alice knows Bob"},
        }]

        with patch("odap.infra.graph.graph_service.GraphManager", return_value=fake_gm):
            result = await GraphWriteStep().execute(
                entities=entities, relations=relations,
                pipeline_run_id="run_1", workspace_id="ws_1",
            )

        assert result.is_success, result.errors

        nprops = fake_gm.add_entity.call_args.kwargs["properties"]
        assert nprops[FIELD_SCHEMA_VERSION] == SCHEMA_VERSION
        assert nprops[FIELD_SOURCE_DOC_IDS] == ["doc_A"]
        assert nprops[FIELD_CHUNK_ID] == "c1"
        assert nprops[FIELD_CONFIDENCE] == 0.91
        # 溯源与 batch/pipeline 字段共存、互不覆盖
        assert nprops["pipeline_run_id"] == "run_1"
        assert nprops["batch_id"] == result.batch_id

        rprops = fake_gm.add_relationship.call_args.kwargs["properties"]
        assert rprops[FIELD_SCHEMA_VERSION] == SCHEMA_VERSION
        assert rprops[FIELD_SOURCE_DOC_IDS] == ["doc_A", "doc_C"]
        assert rprops[FIELD_EVIDENCE_TEXT] == "Alice knows Bob"


# ── NormalizationStep merge 不再丢失溯源 ──────────────────────────────

class TestNormalizationMergeKeepsProvenance:
    @pytest.mark.asyncio
    async def test_merge_unions_doc_ids_and_preserves_chunk(self):
        from odap.biz.core.ontology.construction.pipeline.services.step_handlers.normalization import (
            NormalizationStep,
        )

        entities = [
            {"id": "e1", "name": "Alice", "properties": {"source_doc_id": "doc_A", "chunk_id": "c1"}},
            {"id": "e2", "name": "Alice", "properties": {"source_doc_id": "doc_B", "confidence": 0.6}},
        ]
        out = await NormalizationStep().execute(entities=entities, ontology_id="o1", workspace_id="ws_1")

        assert out.merge_count == 1
        assert len(out.entities) == 1
        props = out.entities[0]["properties"]
        # 关键回归：merge 前 chunk_id / source_doc_ids 会被抹掉，冻结后必须保留
        assert set(props[FIELD_SOURCE_DOC_IDS]) == {"doc_A", "doc_B"}
        assert props[FIELD_CHUNK_ID] == "c1"
        assert props[FIELD_CONFIDENCE] == 0.6
        assert props[FIELD_SCHEMA_VERSION] == SCHEMA_VERSION
