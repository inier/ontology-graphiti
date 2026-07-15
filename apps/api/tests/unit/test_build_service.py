"""测试本体构建服务 (OntologyBuilderService)"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field


def _make_entity(entity_id="entity-001", entity_type="Unit", name="测试实体", **overrides):
    from odap.biz.core.ontology.design.schema.document import OntologyEntity
    defaults = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "name_en": "",
        "aliases": [],
        "basic_properties": {},
        "statistical_properties": {},
        "capabilities": {},
        "constraints": [],
    }
    defaults.update(overrides)
    return OntologyEntity(**defaults)


def _make_relation(relation_id="rel-001", relation_type="related_to",
                   source_entity="entity-001", target_entity="entity-002", **overrides):
    from odap.biz.core.ontology.design.schema.document import OntologyRelation, TemporalInfo
    defaults = {
        "relation_id": relation_id,
        "relation_type": relation_type,
        "source_entity": source_entity,
        "target_entity": target_entity,
        "properties": {},
        "temporal": TemporalInfo(),
    }
    defaults.update(overrides)
    return OntologyRelation(**defaults)


def _make_event(event_id="evt-001", event_type="generic", **overrides):
    from odap.biz.core.ontology.design.schema.document import OntologyEvent
    defaults = {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2025-01-01T00:00:00Z",
        "location": "",
        "coordinates": None,
        "participants": [],
        "description": "测试事件",
        "outcome": {},
        "phase": "",
    }
    defaults.update(overrides)
    return OntologyEvent(**defaults)


def _make_document(doc_id="doc-20250101-abc123", **overrides):
    from odap.biz.core.ontology.design.schema.document import OntologyDocument, DocumentMeta
    defaults = {
        "doc_id": doc_id,
        "meta": DocumentMeta(title="测试本体"),
        "entities": [_make_entity()],
        "relations": [],
        "events": [],
    }
    defaults.update(overrides)
    return OntologyDocument(**defaults)


@pytest.fixture
def build_service():
    from odap.biz.core.ontology.design.services.build_service import OntologyBuilderService
    return OntologyBuilderService()


class TestBuildOntologySuccess:
    @pytest.mark.asyncio
    async def test_build_returns_completed_status(self, build_service):
        """构建成功时返回 completed 状态"""
        doc = _make_document()
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["status"] == "completed"
        assert result["build_id"].startswith("build-")

    @pytest.mark.asyncio
    async def test_build_extracts_entities(self, build_service):
        """构建时正确提取实体"""
        entities = [_make_entity(entity_id="e1"), _make_entity(entity_id="e2")]
        doc = _make_document(entities=entities)
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["stats"]["entities_extracted"] == 2

    @pytest.mark.asyncio
    async def test_build_extracts_relations(self, build_service):
        """构建时正确提取关系"""
        relations = [_make_relation(), _make_relation(relation_id="rel-002")]
        doc = _make_document(
            entities=[_make_entity(entity_id="e1"), _make_entity(entity_id="e2")],
            relations=relations,
        )
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["stats"]["relations_extracted"] == 2

    @pytest.mark.asyncio
    async def test_build_creates_nodes_and_edges(self, build_service):
        """构建时创建图谱节点和边"""
        doc = _make_document(
            entities=[_make_entity(entity_id="e1"), _make_entity(entity_id="e2")],
            relations=[_make_relation(source_entity="e1", target_entity="e2")],
        )
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["stats"]["nodes_created"] >= 2
        assert result["stats"]["edges_created"] >= 1


class TestBuildOntologyErrors:
    @pytest.mark.asyncio
    async def test_build_failure_returns_failed_status(self, build_service):
        """构建失败时返回 failed 状态"""
        doc = _make_document()
        with patch.object(build_service, '_extract_entities_relations', new_callable=AsyncMock, side_effect=Exception("提取失败")):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["status"] == "failed"
        assert "提取失败" in result["error"]

    @pytest.mark.asyncio
    async def test_build_without_version(self, build_service):
        """不创建版本时 version_info 为 None"""
        doc = _make_document()
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock):
            result = await build_service.build_ontology(doc, scenario_id="sc-001", create_new_version=False)
        assert result["version_info"] is None
        assert result["status"] == "completed"


class TestBuildOntologyEvents:
    @pytest.mark.asyncio
    async def test_build_extracts_events_as_entities(self, build_service):
        """事件被提取为实体"""
        events = [_make_event(event_id="evt-1", event_type="attack", participants=["entity-001"])]
        doc = _make_document(events=events)
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        # 1 entity + 1 event entity
        assert result["stats"]["entities_extracted"] == 2
        # 1 participated_in relation from event
        assert result["stats"]["relations_extracted"] == 1


class TestDetectChanges:
    @pytest.mark.asyncio
    async def test_detect_changes_marks_all_as_added(self, build_service):
        """变化检测将新文档所有实体标记为 added"""
        doc = _make_document(
            entities=[_make_entity(entity_id="e1"), _make_entity(entity_id="e2")],
            relations=[_make_relation()],
        )
        result = await build_service.detect_changes(doc, current_graph_version="v1")
        assert "e1" in result["entities"]["added"]
        assert "e2" in result["entities"]["added"]
        assert "rel-001" in result["relations"]["added"]


class TestRollbackVersion:
    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version_returns_error(self, build_service):
        """回滚不存在的版本返回错误"""
        with patch("odap.biz.core.ontology.design.services.build_service.SQLiteIngestStorage",
                   create=True) as MockStorage:
            mock_storage = MagicMock()
            mock_storage.get_version.return_value = None
            MockStorage.return_value = mock_storage
            result = await build_service.rollback_version("nonexistent-v", "sc-001")
        assert result["status"] == "error"
        assert "不存在" in result["message"]


class TestBuildProgress:
    @pytest.mark.asyncio
    async def test_build_progress_reaches_100(self, build_service):
        """构建成功时进度达到 100"""
        doc = _make_document()
        with patch.object(build_service, '_write_to_graphiti', new_callable=AsyncMock), \
             patch.object(build_service, '_create_version', new_callable=AsyncMock, return_value={"version_id": "v1"}):
            result = await build_service.build_ontology(doc, scenario_id="sc-001")
        assert result["progress"] == 100.0
