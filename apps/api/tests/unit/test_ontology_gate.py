"""OntologyGate 门控服务单元测试"""
import pytest
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

from odap.biz.data.qa.ontology_gate import (
    OntologySchema,
    QueryValidation,
    ResultValidation,
    OntologyGate,
)


# ── OntologySchema 测试 ──


class TestOntologySchema:
    def test_default_values(self):
        schema = OntologySchema(ontology_id="test")
        assert schema.ontology_id == "test"
        assert schema.entity_types == {}
        assert schema.relation_types == {}
        assert schema.entity_type_names == set()
        assert schema.relation_type_names == set()
        assert schema.property_names_by_type == {}

    def test_with_entity_types(self):
        schema = OntologySchema(
            ontology_id="test",
            entity_types={"Unit": {"display_name": "单位", "properties": ["name"], "links": []}},
            entity_type_names={"Unit"},
            property_names_by_type={"Unit": {"name"}},
        )
        assert "Unit" in schema.entity_type_names
        assert "name" in schema.property_names_by_type["Unit"]

    def test_with_relation_types(self):
        schema = OntologySchema(
            ontology_id="test",
            relation_types={"belongs_to": {"source_type": "Unit", "target_type": "Org"}},
            relation_type_names={"belongs_to"},
        )
        assert "belongs_to" in schema.relation_type_names


# ── QueryValidation 测试 ──


class TestQueryValidation:
    def test_default_values(self):
        qv = QueryValidation()
        assert qv.is_valid is True
        assert qv.matched_entity_types == []
        assert qv.matched_relation_types == []
        assert qv.suggested_types == []
        assert qv.confidence == 1.0


# ── ResultValidation 测试 ──


class TestResultValidation:
    def test_default_values(self):
        rv = ResultValidation()
        assert rv.total == 0
        assert rv.ontology_aligned == 0
        assert rv.score_adjustments == {}


# ── 输入门控测试 ──


@dataclass
class FakeRAGResult:
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestOntologyGateInputGating:
    def _make_schema(self, entity_types=None, relation_types=None):
        schema = OntologySchema(ontology_id="test-ont")
        for et in (entity_types or []):
            name = et if isinstance(et, str) else et["name"]
            schema.entity_types[name] = {"display_name": "", "properties": [], "links": []}
            schema.entity_type_names.add(name)
        for rt in (relation_types or []):
            name = rt if isinstance(rt, str) else rt["name"]
            schema.relation_types[name] = {"source_type": "", "target_type": ""}
            schema.relation_type_names.add(name)
        return schema

    def test_no_schema_passthrough(self):
        gate = OntologyGate()
        qv = gate.validate_query("孙悟空是谁", [])
        assert qv.is_valid is True
        assert qv.confidence == 1.0

    def test_match_entity_type_name(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["西游人物", "法宝"])
        qv = gate.validate_query("西游人物有哪些", [schema])
        assert "西游人物" in qv.matched_entity_types
        assert qv.confidence == 1.0

    def test_match_display_name(self):
        gate = OntologyGate()
        schema = OntologySchema(ontology_id="test-ont")
        schema.entity_types["Unit"] = {"display_name": "作战单位", "properties": [], "links": []}
        schema.entity_type_names.add("Unit")
        qv = gate.validate_query("作战单位有哪些", [schema])
        assert "Unit" in qv.matched_entity_types

    def test_match_relation_type(self):
        gate = OntologyGate()
        schema = self._make_schema(relation_types=["belongs_to", "commands"])
        qv = gate.validate_query("谁 belongs_to 哪个组织", [schema])
        assert "belongs_to" in qv.matched_relation_types

    def test_no_match_degrade_not_reject(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit", "Equipment"])
        qv = gate.validate_query("孙悟空是谁", [schema])
        assert qv.is_valid is True  # 不拒绝
        assert qv.confidence == 0.6  # 但降级

    def test_multiple_schemas_merged(self):
        gate = OntologyGate()
        s1 = self._make_schema(entity_types=["Unit"])
        s2 = self._make_schema(entity_types=["西游人物"])
        qv = gate.validate_query("西游人物和Unit", [s1, s2])
        assert "Unit" in qv.matched_entity_types
        assert "西游人物" in qv.matched_entity_types


# ── 输出门控测试 ──


class TestOntologyGateOutputGating:
    def _make_schema(self, entity_types=None):
        schema = OntologySchema(ontology_id="test-ont")
        for et in (entity_types or []):
            schema.entity_types[et] = {"display_name": "", "properties": [], "links": []}
            schema.entity_type_names.add(et)
        return schema

    def test_no_schema_passthrough(self):
        gate = OntologyGate()
        results = [FakeRAGResult(content="test", source="s", score=0.9, metadata={"entity_type": "X"})]
        rv = gate.validate_results(results, [])
        assert rv.total == 1
        assert rv.score_adjustments == {}

    def test_empty_results(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit"])
        rv = gate.validate_results([], [schema])
        assert rv.total == 0

    def test_aligned_result(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit"])
        results = [FakeRAGResult(content="test", source="s", score=0.9, metadata={"entity_type": "Unit"})]
        rv = gate.validate_results(results, [schema])
        assert rv.ontology_aligned == 1
        assert 0 not in rv.score_adjustments

    def test_misaligned_penalty(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit"])
        results = [FakeRAGResult(content="test", source="s", score=0.9, metadata={"entity_type": "Unknown"})]
        rv = gate.validate_results(results, [schema])
        assert 0 in rv.score_adjustments
        assert rv.score_adjustments[0] == pytest.approx(0.45)  # 0.9 * 0.5

    def test_no_type_slight_penalty(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit"])
        results = [FakeRAGResult(content="test", source="s", score=0.9, metadata={})]
        rv = gate.validate_results(results, [schema])
        assert 0 in rv.score_adjustments
        assert rv.score_adjustments[0] == pytest.approx(0.72)  # 0.9 * 0.8

    def test_apply_adjustments(self):
        gate = OntologyGate()
        schema = self._make_schema(entity_types=["Unit"])
        results = [
            FakeRAGResult(content="good", source="s1", score=0.9, metadata={"entity_type": "Unit"}),
            FakeRAGResult(content="bad", source="s2", score=0.8, metadata={"entity_type": "Unknown"}),
        ]
        rv = gate.validate_results(results, [schema])
        adjusted = gate.apply_score_adjustments(results, rv)
        assert adjusted[0].score == 0.9  # 对齐的不变
        assert adjusted[1].score == pytest.approx(0.4)  # 0.8 * 0.5

    def test_no_adjustments_return_same(self):
        gate = OntologyGate()
        results = [FakeRAGResult(content="test", source="s", score=0.9)]
        rv = ResultValidation(total=1)
        adjusted = gate.apply_score_adjustments(results, rv)
        assert adjusted[0].score == 0.9


# ── Schema 缓存测试 ──


class TestOntologyGateSchemaCaching:
    def test_cache_hit(self):
        gate = OntologyGate()
        schema = OntologySchema(ontology_id="cached-ont", entity_type_names={"Unit"})
        gate._schema_cache["default:cached-ont"] = schema
        gate._cache_timestamps["default:cached-ont"] = time.time()

        schemas = gate.load_schema(["cached-ont"], "default")
        assert len(schemas) == 1
        assert schemas[0].ontology_id == "cached-ont"

    def test_cache_expired(self):
        gate = OntologyGate()
        schema = OntologySchema(ontology_id="expired-ont", entity_type_names={"Unit"})
        gate._schema_cache["default:expired-ont"] = schema
        gate._cache_timestamps["default:expired-ont"] = time.time() - 600  # 10分钟前

        with patch.object(gate, '_load_schema_from_storage', return_value=None):
            schemas = gate.load_schema(["expired-ont"], "default")
        assert len(schemas) == 0  # 过期且加载失败

    def test_none_ontology_ids(self):
        gate = OntologyGate()
        schemas = gate.load_schema(None, "default")
        assert schemas == []

    def test_empty_ontology_ids(self):
        gate = OntologyGate()
        schemas = gate.load_schema([], "default")
        assert schemas == []

    def test_storage_failure(self):
        gate = OntologyGate()
        with patch.object(gate, '_load_schema_from_storage', side_effect=Exception("storage error")):
            schemas = gate.load_schema(["bad-ont"], "default")
        assert schemas == []


# ── 向后兼容测试 ──


class TestOntologyGateBackwardCompatibility:
    def test_no_schema_query_validation(self):
        gate = OntologyGate()
        qv = gate.validate_query("任意查询", [])
        assert qv.is_valid is True
        assert qv.confidence == 1.0

    def test_no_schema_result_validation(self):
        gate = OntologyGate()
        results = [FakeRAGResult(content="test", source="s", score=0.9)]
        rv = gate.validate_results(results, [])
        assert rv.score_adjustments == {}

    def test_no_adjustments_passthrough(self):
        gate = OntologyGate()
        results = [FakeRAGResult(content="test", source="s", score=0.9)]
        rv = ResultValidation(total=1)
        adjusted = gate.apply_score_adjustments(results, rv)
        assert len(adjusted) == 1
        assert adjusted[0].score == 0.9
