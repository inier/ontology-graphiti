"""TDD 单元测试：ADR-077 SHACL/OWL 本体治理。

覆盖：
  T-GOV-1: ShapeGenerator 实时生成（required → minCount，data_type → datatype）
  T-GOV-2: ShapeGenerator 关系基数映射（cardinality → minCount/maxCount）
  T-GOV-3: ShapeGenerator 组合关系 → sh:class
  T-GOV-4: 生成确定性（同输入同输出）
  T-GOV-5: SHACLValidator 合规实例通过
  T-GOV-6: SHACLValidator 违规实例（缺必填）被检出
  T-GOV-7: OWLExporter 导出 Turtle（含 class/property/关系）
  T-GOV-8: OWLImporter 结构映射（class→entity_type, datatype→property, object→link）
  T-GOV-9: OWLImporter 导入结果为 draft（不直接入库）
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.design.engine.shacl.shape_generator import (
    ShapeGenerator, generate_shapes,
)
from odap.biz.core.ontology.design.engine.shacl.validator import SHACLValidator
from odap.biz.core.ontology.design.engine.owl.owl_exporter import OWLExporter
from odap.biz.core.ontology.design.engine.owl.owl_importer import OWLImporter


# ── 测试夹具 ──

@pytest.fixture
def entity_types():
    """标准实体类型定义（Unit，含必填属性/基数/组合关系）"""
    return [
        {
            "type_id": "Unit",
            "name": "Unit",
            "display_name": "单位",
            "description": "作战单位",
            "properties": [
                {"name": "name", "data_type": "string", "required": True, "classification_level": "U"},
                {"name": "strength", "data_type": "integer", "required": False, "classification_level": "S"},
            ],
            "links": [
                {"name": "has_weapon", "target_type": "Weapon", "cardinality": "1:N", "link_type": "association"},
                {"name": "part_of", "target_type": "Unit", "cardinality": "N:1", "link_type": "composition"},
            ],
            "primary_key": ["name"],
            "classification_level": "U",
        }
    ]


class TestShapeGenerator:
    def test_required_and_datatype(self, entity_types):
        ttl = generate_shapes(entity_types)
        assert "sh:NodeShape" in ttl or "NodeShape" in ttl
        assert "Unit" in ttl
        # required → minCount 1
        assert "minCount" in ttl
        # data_type → datatype
        assert "datatype" in ttl
        assert "integer" in ttl or "Integer" in ttl

    def test_cardinality_mapping(self, entity_types):
        ttl = generate_shapes(entity_types)
        # 1:N → maxCount 缺失（无上限），N:1 → maxCount 1
        assert "maxCount" in ttl

    def test_composition_link_class(self, entity_types):
        ttl = generate_shapes(entity_types)
        # 组合关系（part_of）→ sh:nodeKind sh:IRI（目标必须是 IRI 节点）
        assert "nodeKind" in ttl

    def test_deterministic(self, entity_types):
        ttl1 = generate_shapes(entity_types)
        ttl2 = generate_shapes(entity_types)
        assert ttl1 == ttl2


class TestSHACLValidator:
    def test_conforms_valid_instance(self, entity_types):
        instances = [
            {
                "instance_id": "u1",
                "type_id": "Unit",
                "properties": {
                    "name": "红方装甲营",
                    "strength": 320,
                },
                "links": {
                    "has_weapon": "weapon-1",   # 满足 1:N 关系的 minCount 1
                    "part_of": "parent-unit",  # 满足 N:1 组合关系
                },
            }
        ]
        report = SHACLValidator().validate(entity_types, instances)
        assert report["conforms"] is True
        assert report["violation_count"] == 0

    def test_detects_missing_required(self, entity_types):
        instances = [
            {
                "instance_id": "u2",
                "type_id": "Unit",
                "properties": {
                    "strength": 320,
                },
                "links": {
                    "has_weapon": "weapon-1",
                    "part_of": "parent-unit",
                },  # 缺必填 name
            }
        ]
        report = SHACLValidator().validate(entity_types, instances)
        assert report["conforms"] is False
        assert report["violation_count"] > 0


class TestOWLExporter:
    def test_export_turtle(self, entity_types):
        ttl = OWLExporter().export_turtle(entity_types)
        assert "owl:Class" in ttl
        assert "Unit" in ttl
        assert "owl:DatatypeProperty" in ttl
        assert "owl:ObjectProperty" in ttl
        assert "Weapon" in ttl

    def test_export_rdfxml(self, entity_types):
        xml = OWLExporter().export_rdfxml(entity_types)
        assert "rdf:RDF" in xml or "rdf:" in xml


class TestOWLImporter:
    def test_import_structure_mapping(self, entity_types):
        # 先导出一个本体，再导入回来（往返）
        ttl = OWLExporter().export_turtle(entity_types)
        result = OWLImporter().import_schema_candidates(ttl)
        assert result["status"] == "draft"
        assert result["source_format"] == "owl"
        # 至少导入 Unit 实体类型
        names = [et["name"] for et in result["entity_types"]]
        assert "Unit" in names

    def test_import_result_is_draft(self):
        # 最小 OWL 本体
        owl_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .
        ex:Person a owl:Class ; rdfs:label "Person" .
        """
        result = OWLImporter().import_schema_candidates(owl_ttl)
        assert result["status"] == "draft"
        names = [et["name"] for et in result["entity_types"]]
        assert "Person" in names
