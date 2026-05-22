import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestTextIngestPipeline:

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_natural_language", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    def test_ingest_text_creates_entities(self, mock_get_status, mock_ingest_nl):
        mock_ingest_nl.return_value = "ingest-abc-123"
        mock_get_status.return_value = {
            "id": "ingest-abc-123",
            "source": "natural_language",
            "status": "completed",
            "original_content": "2024年1月，第3舰队部署了5艘驱逐舰到太平洋区域进行例行巡逻。",
            "extracted_data": {
                "entities": [
                    {"name": "第3舰队", "type": "MilitaryUnit"},
                    {"name": "太平洋", "type": "Location"},
                    {"name": "驱逐舰", "type": "Equipment"}
                ],
                "relations": [
                    {"source": "第3舰队", "target": "太平洋", "type": "deployed_to"}
                ],
                "document_count": 1
            },
            "source_details": {"text_length": 30},
            "record_count": 1
        }
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "2024年1月，第3舰队部署了5艘驱逐舰到太平洋区域进行例行巡逻。",
                "scenario_id": "default"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "ingest_id" in data
        assert data["status"] == "completed"
        assert data["extracted_data"] is not None
        assert "entities" in data["extracted_data"]
        assert len(data["extracted_data"]["entities"]) > 0

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_natural_language", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    def test_ingest_text_with_scenario(self, mock_get_status, mock_ingest_nl):
        scenario_id = str(uuid.uuid4())
        mock_ingest_nl.return_value = "ingest-scenario-456"
        mock_get_status.return_value = {
            "id": "ingest-scenario-456",
            "source": "natural_language",
            "status": "completed",
            "original_content": "军事演习在南海举行",
            "extracted_data": {
                "entities": [{"name": "南海", "type": "Location"}],
                "relations": [],
                "document_count": 1
            },
            "source_details": {"text_length": 9},
            "record_count": 1
        }
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "军事演习在南海举行",
                "scenario_id": scenario_id
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ingest_id"] == "ingest-scenario-456"
        mock_ingest_nl.assert_called_once_with("军事演习在南海举行", scenario_id)

    def test_ingest_text_empty(self):
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": ""
            }
        )
        assert response.status_code in [400, 422]

        response = client.post(
            "/api/ontology/ingest/natural-language",
            json={"data": ""}
        )
        assert response.status_code in [400, 422]


class TestNewsIngestPipeline:

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_news", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    def test_ingest_news(self, mock_get_status, mock_ingest_news):
        mock_ingest_news.return_value = "ingest-news-789"
        mock_get_status.return_value = {
            "id": "ingest-news-789",
            "source": "news",
            "status": "completed",
            "original_content": "Breaking: Pacific fleet exercise",
            "extracted_data": {
                "document_count": 2,
                "search_engine": "duckduckgo"
            },
            "source_details": {"query": "Pacific fleet exercise", "max_sources": 5},
            "record_count": 2
        }
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "news",
                "data": "Pacific fleet exercise",
                "event_context": "military",
                "max_sources": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "ingest_id" in data
        assert data["status"] == "completed"

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_news", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    def test_ingest_news_extracts_entities(self, mock_get_status, mock_ingest_news):
        mock_ingest_news.return_value = "ingest-news-entity-001"
        mock_get_status.return_value = {
            "id": "ingest-news-entity-001",
            "source": "news",
            "status": "completed",
            "original_content": "US Navy deploys carrier strike group to South China Sea",
            "extracted_data": {
                "entities": [
                    {"name": "US Navy", "type": "MilitaryUnit"},
                    {"name": "South China Sea", "type": "Location"},
                    {"name": "carrier strike group", "type": "Equipment"}
                ],
                "relations": [
                    {"source": "US Navy", "target": "South China Sea", "type": "deployed_to"}
                ],
                "document_count": 3,
                "search_engine": "duckduckgo"
            },
            "source_details": {"query": "South China Sea deployment", "max_sources": 5},
            "record_count": 3
        }
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "news",
                "data": "South China Sea deployment",
                "event_context": "military deployment",
                "max_sources": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["extracted_data"] is not None
        assert "entities" in data["extracted_data"]
        assert len(data["extracted_data"]["entities"]) >= 1
        assert "relations" in data["extracted_data"]


class TestOntologyBuildPipeline:

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_natural_language", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    @patch("odap.biz.ontology.api.routes.SQLiteIngestStorage.save_build_history")
    def test_build_after_ingest(self, mock_save_build, mock_get_status, mock_ingest_nl):
        mock_ingest_nl.return_value = "ingest-build-test-001"
        mock_get_status.return_value = {
            "id": "ingest-build-test-001",
            "source": "natural_language",
            "status": "completed",
            "original_content": "军事演习在东海举行，参演兵力包括2艘驱逐舰",
            "start_time": "2026-01-15T10:00:00",
            "extracted_data": {
                "entities": [{"name": "东海", "type": "Location"}],
                "relations": [],
                "document_count": 1
            },
            "source_details": {"text_length": 20},
            "record_count": 1
        }
        ingest_response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "军事演习在东海举行，参演兵力包括2艘驱逐舰",
                "scenario_id": "default"
            }
        )
        assert ingest_response.status_code == 200
        ingest_id = ingest_response.json()["ingest_id"]

        with patch("odap.biz.ontology.api.routes.get_pipeline_service") as mock_pipeline_svc:
            mock_context = MagicMock()
            mock_context.success = True
            mock_context.version_id = "ver-001"
            mock_context.document_id = "doc-001"
            mock_context.stage_results = {
                "ontology": {"entity_count": 5, "relation_count": 2},
                "llm": {"event_count": 3}
            }
            mock_pipeline_svc.return_value.run = AsyncMock(return_value=mock_context)

            build_response = client.post(
                f"/api/ontology/ingest/{ingest_id}/build",
                json={"scenario_id": "default"}
            )
            assert build_response.status_code == 200
            build_data = build_response.json()
            assert "build_id" in build_data
            assert build_data["status"] == "pending"

    @patch("odap.biz.ontology.services.ingest_service.IngestService.ingest_from_natural_language", new_callable=AsyncMock)
    @patch("odap.biz.ontology.services.ingest_service.IngestService.get_ingest_status")
    @patch("odap.biz.ontology.api.routes.SQLiteIngestStorage.save_build_history")
    def test_version_snapshot(self, mock_save_build, mock_get_status, mock_ingest_nl):
        mock_ingest_nl.return_value = "ingest-version-001"
        mock_get_status.return_value = {
            "id": "ingest-version-001",
            "source": "natural_language",
            "status": "completed",
            "original_content": "测试版本快照内容",
            "start_time": "2026-01-15T10:00:00",
            "extracted_data": {
                "entities": [{"name": "测试实体", "type": "TestEntity"}],
                "relations": [],
                "document_count": 1
            },
            "source_details": {"text_length": 8},
            "record_count": 1
        }
        ingest_response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "测试版本快照内容",
                "scenario_id": "default"
            }
        )
        assert ingest_response.status_code == 200
        ingest_id = ingest_response.json()["ingest_id"]

        with patch("odap.biz.ontology.api.routes.get_pipeline_service") as mock_pipeline_svc:
            mock_context = MagicMock()
            mock_context.success = True
            mock_context.version_id = "ver-snapshot-001"
            mock_context.document_id = "doc-snapshot-001"
            mock_context.stage_results = {
                "ontology": {"entity_count": 1, "relation_count": 0},
                "llm": {"event_count": 0}
            }
            mock_pipeline_svc.return_value.run = AsyncMock(return_value=mock_context)

            build_response = client.post(
                f"/api/ontology/ingest/{ingest_id}/build",
                json={"scenario_id": "default"}
            )
            assert build_response.status_code == 200

        with patch("odap.biz.ontology.api.routes.ingest_service") as mock_svc:
            mock_svc.get_ingest_status.return_value = {
                "id": ingest_id,
                "status": "completed",
                "builds": [
                    {
                        "build_id": "build-version-001",
                        "status": "completed",
                        "document_id": "doc-snapshot-001",
                        "version_info": {"version_id": "ver-snapshot-001"}
                    }
                ]
            }
            status_response = client.get(f"/api/ontology/ingest/{ingest_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert "builds" in status_data or "build_status" in status_data


class TestIngestErrorHandling:

    def test_invalid_source(self):
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "invalid_source_type",
                "data": "some data"
            }
        )
        assert response.status_code == 400
        assert "Invalid source type" in response.json().get("detail", "")

    def test_missing_text_field(self):
        response = client.post(
            "/api/ontology/ingest/natural-language",
            json={}
        )
        assert response.status_code == 422

        response = client.post(
            "/api/ontology/ingest",
            json={"source_type": "natural_language"}
        )
        assert response.status_code in [400, 422, 500]
