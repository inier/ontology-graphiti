import pytest
import os
from datetime import datetime
from unittest.mock import MagicMock, patch


def _make_entity(**overrides):
    defaults = {
        "entity_id": "entity-test-001",
        "entity_type": "Unit",
        "name": "测试单位",
        "name_en": "TestUnit",
        "aliases": ["测试"],
        "basic_properties": {"side": "red", "status": "active"},
        "statistical_properties": {"combat_power": 0.8},
        "capabilities": {"fire_range_km": 10},
        "confidence": 0.95,
    }
    defaults.update(overrides)
    return defaults


def _make_relation(**overrides):
    defaults = {
        "id": "rel-001",
        "source": "entity-test-001",
        "target": "entity-test-002",
        "type": "engaged_with",
        "properties": {"engagement_type": "direct_fire"},
    }
    defaults.update(overrides)
    return defaults


class TestSemanticMapModels:
    def test_semantic_map_status_enum(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapStatus
        assert SemanticMapStatus.DRAFT == "draft"
        assert SemanticMapStatus.GENERATING == "generating"
        assert SemanticMapStatus.COMPLETED == "completed"
        assert SemanticMapStatus.FAILED == "failed"

    def test_semantic_map_object_defaults(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapObject
        obj = SemanticMapObject(entity_id="e1", object_type="Unit", name="Test")
        assert obj.object_id
        assert obj.entity_id == "e1"
        assert obj.object_type == "Unit"
        assert obj.name == "Test"
        assert obj.properties == {}
        assert obj.relation_ids == []
        assert obj.cluster is None
        assert obj.confidence == 1.0

    def test_semantic_map_relation_defaults(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapRelation
        rel = SemanticMapRelation(
            source_object_id="o1", target_object_id="o2", relation_type="related_to"
        )
        assert rel.relation_id
        assert rel.source_object_id == "o1"
        assert rel.target_object_id == "o2"
        assert rel.relation_type == "related_to"
        assert rel.is_bidirectional is False
        assert rel.is_current is True

    def test_semantic_map_cluster(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapCluster
        cluster = SemanticMapCluster(
            cluster_id="c1", cluster_name="Unit", cluster_type="entity_type"
        )
        assert cluster.cluster_id == "c1"
        assert cluster.object_ids == []

    def test_semantic_map_statistics_defaults(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapStatistics
        stats = SemanticMapStatistics()
        assert stats.total_objects == 0
        assert stats.total_relations == 0
        assert stats.objects_by_type == {}
        assert stats.coverage_score == 0.0

    def test_semantic_map_full(self):
        from odap.biz.data.semantic_map.models.semantic_map import (
            SemanticMap, SemanticMapObject, SemanticMapStatus,
        )
        obj = SemanticMapObject(entity_id="e1", object_type="Unit", name="Test")
        sm = SemanticMap(
            name="测试语义地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            objects=[obj],
        )
        assert sm.id
        assert sm.name == "测试语义地图"
        assert sm.status == SemanticMapStatus.DRAFT
        assert len(sm.objects) == 1
        assert sm.created_by == "system"

    def test_semantic_map_status_must_be_str_enum(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapStatus
        assert isinstance(SemanticMapStatus.DRAFT, str)
        assert SemanticMapStatus.DRAFT.value == "draft"

    def test_semantic_map_object_with_type_definition(self):
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMapObject
        obj = SemanticMapObject(
            entity_id="e1",
            object_type="Unit",
            name="Test",
            type_definition_id="type-unit",
            type_definition_name="军事单位",
        )
        assert obj.type_definition_id == "type-unit"
        assert obj.type_definition_name == "军事单位"


class TestSQLiteSemanticMapStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        assert os.path.exists(db_path)

    def test_save_and_get(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import (
            SemanticMap, SemanticMapObject, SemanticMapStatus,
        )
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        obj = SemanticMapObject(entity_id="e1", object_type="Unit", name="Test")
        sm = SemanticMap(
            name="测试地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            status=SemanticMapStatus.COMPLETED,
            objects=[obj],
        )

        map_id = storage.save(sm)
        assert map_id == sm.id

        retrieved = storage.get(map_id)
        assert retrieved is not None
        assert retrieved.name == "测试地图"
        assert retrieved.status == SemanticMapStatus.COMPLETED
        assert len(retrieved.objects) == 1
        assert retrieved.objects[0].entity_id == "e1"

    def test_get_not_found(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        result = storage.get("nonexistent")
        assert result is None

    def test_list_by_version(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMap
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm1 = SemanticMap(name="地图1", ontology_version_id="v1", ontology_id="ont1")
        sm2 = SemanticMap(name="地图2", ontology_version_id="v1", ontology_id="ont1")
        sm3 = SemanticMap(name="地图3", ontology_version_id="v2", ontology_id="ont2")

        storage.save(sm1)
        storage.save(sm2)
        storage.save(sm3)

        v1_maps = storage.list_by_version("v1")
        assert len(v1_maps) == 2

        v2_maps = storage.list_by_version("v2")
        assert len(v2_maps) == 1

    def test_list_by_ontology(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMap
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm1 = SemanticMap(name="地图1", ontology_version_id="v1", ontology_id="ont1")
        sm2 = SemanticMap(name="地图2", ontology_version_id="v2", ontology_id="ont2")

        storage.save(sm1)
        storage.save(sm2)

        ont1_maps = storage.list_by_ontology("ont1")
        assert len(ont1_maps) == 1
        assert ont1_maps[0].name == "地图1"

    def test_list_by_scenario(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMap
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm1 = SemanticMap(
            name="地图1", ontology_version_id="v1", ontology_id="ont1", scenario_id="sc1"
        )
        storage.save(sm1)

        sc1_maps = storage.list_by_scenario("sc1")
        assert len(sc1_maps) == 1

    def test_update_status(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import (
            SemanticMap, SemanticMapStatus,
        )
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm = SemanticMap(name="测试", ontology_version_id="v1", ontology_id="ont1")
        storage.save(sm)

        success = storage.update_status(sm.id, SemanticMapStatus.GENERATING)
        assert success is True

        updated = storage.get(sm.id)
        assert updated.status == SemanticMapStatus.GENERATING

    def test_update_status_with_error(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import (
            SemanticMap, SemanticMapStatus,
        )
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm = SemanticMap(name="测试", ontology_version_id="v1", ontology_id="ont1")
        storage.save(sm)

        storage.update_status(sm.id, SemanticMapStatus.FAILED, "生成失败")
        updated = storage.get(sm.id)
        assert updated.status == SemanticMapStatus.FAILED
        assert updated.error_message == "生成失败"

    def test_delete(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMap
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        sm = SemanticMap(name="测试", ontology_version_id="v1", ontology_id="ont1")
        storage.save(sm)

        success = storage.delete(sm.id)
        assert success is True

        deleted = storage.get(sm.id)
        assert deleted is None

    def test_delete_not_found(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        success = storage.delete("nonexistent")
        assert success is False

    def test_json_serialization_complex(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import (
            SemanticMap, SemanticMapObject, SemanticMapRelation,
            SemanticMapCluster, SemanticMapStatistics, SemanticMapStatus,
        )
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        obj = SemanticMapObject(
            entity_id="e1",
            object_type="Unit",
            name="测试单位",
            aliases=["别名1", "别名2"],
            properties={"basic": {"side": "red"}, "statistical": {"power": 0.9}},
            type_definition_id="type-unit",
            type_definition_name="军事单位",
        )
        rel = SemanticMapRelation(
            source_object_id=obj.object_id,
            target_object_id="other-id",
            relation_type="engaged_with",
            display_name="交战",
            properties={"intensity": "high"},
            is_bidirectional=True,
        )
        cluster = SemanticMapCluster(
            cluster_id="cluster-unit",
            cluster_name="Unit",
            cluster_type="entity_type",
            object_ids=[obj.object_id],
            properties={"count": 1},
        )
        stats = SemanticMapStatistics(
            total_objects=1,
            total_relations=1,
            total_clusters=1,
            objects_by_type={"Unit": 1},
            relations_by_type={"engaged_with": 1},
            avg_relations_per_object=1.0,
            coverage_score=1.0,
        )

        sm = SemanticMap(
            name="完整测试",
            description="复杂序列化测试",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
            status=SemanticMapStatus.COMPLETED,
            objects=[obj],
            relations=[rel],
            clusters=[cluster],
            statistics=stats,
            generation_config={"include_events": True},
        )

        storage.save(sm)
        retrieved = storage.get(sm.id)

        assert retrieved.name == "完整测试"
        assert retrieved.status == SemanticMapStatus.COMPLETED
        assert len(retrieved.objects) == 1
        assert retrieved.objects[0].aliases == ["别名1", "别名2"]
        assert retrieved.objects[0].type_definition_id == "type-unit"
        assert len(retrieved.relations) == 1
        assert retrieved.relations[0].is_bidirectional is True
        assert len(retrieved.clusters) == 1
        assert retrieved.statistics.total_objects == 1
        assert retrieved.statistics.coverage_score == 1.0
        assert retrieved.generation_config == {"include_events": True}

    def test_list_all(self, tmp_path):
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.models.semantic_map import SemanticMap
        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)

        for i in range(5):
            sm = SemanticMap(name=f"地图{i}", ontology_version_id=f"v{i}", ontology_id=f"ont{i}")
            storage.save(sm)

        all_maps = storage.list_all(limit=3)
        assert len(all_maps) == 3


class TestSemanticMapGenerator:
    def test_generate_empty(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        gen = SemanticMapGenerator()
        result = gen.generate(
            name="空地图",
            ontology_version_id="v1",
            ontology_id="ont1",
        )
        assert result.name == "空地图"
        assert result.ontology_version_id == "v1"
        assert result.ontology_id == "ont1"
        assert result.status.value == "completed"
        assert len(result.objects) == 0
        assert len(result.relations) == 0

    def test_generate_with_entities(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", entity_type="Unit", name="红方单位"),
            _make_entity(entity_id="e2", entity_type="Equipment", name="坦克A"),
        ]

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="实体地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert result.status.value == "completed"
        assert len(result.objects) == 2
        assert result.objects[0].name == "红方单位"
        assert result.objects[0].object_type == "Unit"
        assert result.objects[1].object_type == "Equipment"

    def test_generate_with_relations(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", name="单位A"),
            _make_entity(entity_id="e2", name="单位B"),
        ]
        mock_ingest.get_scenario_relations.return_value = {
            "links": [_make_relation(source="e1", target="e2", type="engaged_with")]
        }

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="关系地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert result.status.value == "completed"
        assert len(result.relations) == 1
        assert result.relations[0].relation_type == "engaged_with"

    def test_generate_with_type_definitions(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_oms = MagicMock()
        mock_oms.list_object_types.return_value = [
            {
                "type_id": "type-unit",
                "name": "Unit",
                "display_name": "军事单位",
                "properties": [
                    {"name": "side", "property_type": "string", "required": True, "display_name": "阵营"},
                ],
            }
        ]
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", entity_type="Unit", name="红方单位"),
        ]

        gen = SemanticMapGenerator(oms_storage=mock_oms, ingest_storage=mock_ingest)
        result = gen.generate(
            name="类型定义地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert len(result.objects) == 1
        obj = result.objects[0]
        assert obj.type_definition_id == "type-unit"
        assert obj.type_definition_name == "军事单位"
        assert "_schema" in obj.properties

    def test_generate_clusters(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", entity_type="Unit", name="单位1"),
            _make_entity(entity_id="e2", entity_type="Unit", name="单位2"),
            _make_entity(entity_id="e3", entity_type="Location", name="地点1"),
        ]

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="聚类地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert len(result.clusters) == 2
        unit_cluster = [c for c in result.clusters if c.cluster_name == "Unit"][0]
        assert len(unit_cluster.object_ids) == 2

    def test_generate_statistics(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", entity_type="Unit", name="单位1"),
            _make_entity(entity_id="e2", entity_type="Location", name="地点1"),
        ]

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="统计地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert result.statistics.total_objects == 2
        assert result.statistics.total_clusters == 2
        assert result.statistics.objects_by_type.get("Unit") == 1
        assert result.statistics.objects_by_type.get("Location") == 1

    def test_generate_with_ontology_id_fallback(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_registry_entities.return_value = [
            _make_entity(entity_id="e1", canonical_id="e1", entity_type="Unit", name="注册实体"),
        ]

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="注册表地图",
            ontology_version_id="v1",
            ontology_id="ont1",
        )

        assert len(result.objects) == 1
        assert result.objects[0].entity_id == "e1"

    def test_generate_failure_handling(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.side_effect = RuntimeError("DB错误")

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="失败地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert result.status.value == "failed"
        assert "DB错误" in result.error_message

    def test_relation_filtering_invalid_entities(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", name="单位A"),
        ]
        mock_ingest.get_scenario_relations.return_value = {
            "links": [
                _make_relation(source="e1", target="e2", type="related_to"),
                _make_relation(source="e3", target="e4", type="related_to"),
            ]
        }

        gen = SemanticMapGenerator(ingest_storage=mock_ingest)
        result = gen.generate(
            name="过滤地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert len(result.relations) == 0

    def test_coverage_score(self):
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator
        mock_oms = MagicMock()
        mock_oms.list_object_types.return_value = [
            {"type_id": "type-unit", "name": "Unit", "display_name": "军事单位", "properties": []},
        ]
        mock_ingest = MagicMock()
        mock_ingest.get_scenario_entities.return_value = [
            _make_entity(entity_id="e1", entity_type="Unit", name="有类型"),
            _make_entity(entity_id="e2", entity_type="Equipment", name="无类型"),
        ]

        gen = SemanticMapGenerator(oms_storage=mock_oms, ingest_storage=mock_ingest)
        result = gen.generate(
            name="覆盖率地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            scenario_id="sc1",
        )

        assert result.statistics.coverage_score == 0.5


class TestSemanticMapService:
    def test_create_semantic_map(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.create_semantic_map(
            name="测试地图",
            ontology_version_id="v1",
            ontology_id="ont1",
            description="测试描述",
        )

        assert result["name"] == "测试地图"
        assert result["status"] == "completed"
        assert result["ontology_version_id"] == "v1"

    def test_create_missing_name(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.create_semantic_map(name="", ontology_version_id="v1", ontology_id="ont1")
        assert result["status"] == "error"
        assert "名称" in result["message"]

    def test_create_missing_version_id(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.create_semantic_map(name="测试", ontology_version_id="", ontology_id="ont1")
        assert result["status"] == "error"

    def test_create_missing_ontology_id(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.create_semantic_map(name="测试", ontology_version_id="v1", ontology_id="")
        assert result["status"] == "error"

    def test_get_semantic_map(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        created = service.create_semantic_map(
            name="测试", ontology_version_id="v1", ontology_id="ont1"
        )
        map_id = created["id"]

        result = service.get_semantic_map(map_id)
        assert result["name"] == "测试"

    def test_get_not_found(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.get_semantic_map("nonexistent")
        assert result["status"] == "error"

    def test_list_semantic_maps(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        service.create_semantic_map(name="地图1", ontology_version_id="v1", ontology_id="ont1")
        service.create_semantic_map(name="地图2", ontology_version_id="v1", ontology_id="ont1")

        result = service.list_semantic_maps(ontology_version_id="v1")
        assert result["total"] == 2

    def test_delete_semantic_map(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        created = service.create_semantic_map(
            name="待删除", ontology_version_id="v1", ontology_id="ont1"
        )

        result = service.delete_semantic_map(created["id"])
        assert result["status"] == "ok"

        get_result = service.get_semantic_map(created["id"])
        assert get_result["status"] == "error"

    def test_delete_not_found(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.delete_semantic_map("nonexistent")
        assert result["status"] == "error"

    def test_get_map_graph(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        created = service.create_semantic_map(
            name="图谱测试", ontology_version_id="v1", ontology_id="ont1"
        )

        result = service.get_map_graph(created["id"])
        assert "nodes" in result
        assert "edges" in result
        assert "clusters" in result
        assert "statistics" in result

    def test_regenerate(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        created = service.create_semantic_map(
            name="重新生成", ontology_version_id="v1", ontology_id="ont1"
        )

        result = service.regenerate(created["id"])
        assert result["name"] == "重新生成"
        assert result["id"] == created["id"]

    def test_regenerate_not_found(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.regenerate("nonexistent")
        assert result["status"] == "error"

    def test_service_returns_flat_dict(self, tmp_path):
        from odap.biz.data.semantic_map.services.semantic_map_service import SemanticMapService
        from odap.biz.data.semantic_map.storage.sqlite_semantic_map_storage import SQLiteSemanticMapStorage
        from odap.biz.data.semantic_map.impl.semantic_map_generator import SemanticMapGenerator

        db_path = str(tmp_path / "test_sm.db")
        storage = SQLiteSemanticMapStorage(db_path=db_path)
        generator = SemanticMapGenerator()
        service = SemanticMapService(storage=storage, generator=generator)

        result = service.create_semantic_map(
            name="扁平字典", ontology_version_id="v1", ontology_id="ont1"
        )

        assert isinstance(result, dict)
        assert isinstance(result["status"], str)
        assert isinstance(result["created_at"], str)


class TestSemanticMapSchemas:
    def test_create_request_validation(self):
        from odap.biz.data.semantic_map.api.schemas import CreateSemanticMapRequest
        req = CreateSemanticMapRequest(
            name="测试", ontology_version_id="v1", ontology_id="ont1"
        )
        assert req.name == "测试"
        assert req.created_by == "system"

    def test_create_request_missing_fields(self):
        from odap.biz.data.semantic_map.api.schemas import CreateSemanticMapRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateSemanticMapRequest()

    def test_response_models(self):
        from odap.biz.data.semantic_map.api.schemas import (
            SemanticMapResponse, SemanticMapListResponse, SemanticMapGraphResponse,
        )
        resp = SemanticMapResponse(
            id="sm1", name="测试", ontology_version_id="v1", ontology_id="ont1", status="completed"
        )
        assert resp.status == "completed"

        list_resp = SemanticMapListResponse(total=0)
        assert list_resp.total == 0

        graph_resp = SemanticMapGraphResponse()
        assert graph_resp.nodes == []
