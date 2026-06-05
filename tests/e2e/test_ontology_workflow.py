import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

SERVICE_AVAILABLE = False
try:
    import httpx
    resp = httpx.get("http://localhost:8000/health", timeout=2.0)
    if resp.status_code == 200:
        SERVICE_AVAILABLE = True
except Exception:
    pass

skip_if_no_service = pytest.mark.skipif(
    not SERVICE_AVAILABLE,
    reason="Full service not running for E2E testing",
)


@pytest.mark.e2e
class TestOntologyDesignerWorkflow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("odap.biz.integration.frontend_compat.api.routes.scenario_store", MagicMock()), \
             patch("odap.biz.integration.frontend_compat.api.routes.workspace_service", MagicMock()), \
             patch("odap.biz.core.ontology.application.api.routes.ingest_service") as mock_ingest, \
             patch("odap.biz.platform.workspace.api.routes.workspace_service") as mock_ws:
            mock_ingest.ingest_from_natural_language = AsyncMock(return_value="ingest-nl-001")
            mock_ingest.ingest_from_manual = AsyncMock(return_value="ingest-manual-001")
            mock_ingest.get_ingest_status = MagicMock(return_value={
                "id": "ingest-001",
                "source": "natural_language",
                "status": "completed",
                "record_count": 1,
                "processed_count": 1,
                "failed_count": 0,
                "start_time": "2026-01-01T00:00:00",
                "original_content": "test",
                "extracted_data": {
                    "entities": [{"name": "TestEntity", "type": "Unit"}],
                    "relations": [],
                },
            })
            mock_ingest.get_ingest_history = MagicMock(return_value=[])
            mock_ingest.get_ontology_documents = MagicMock(return_value=[])
            mock_ws.create_workspace = MagicMock(side_effect=lambda **kw: {
                "workspace_id": f"ws-{uuid.uuid4().hex[:8]}",
                "name": kw.get("name", "unnamed"),
                "description": kw.get("description", ""),
                "type": kw.get("workspace_type", "default"),
                "status": "active",
                "created_at": "2026-01-01T00:00:00",
            })
            mock_ws.list_workspaces = MagicMock(return_value={
                "workspaces": [],
                "page": 1,
                "page_size": 10,
                "total": 0,
            })
            mock_ws.get_workspace = MagicMock(return_value={
                "status": "error",
                "message": "Workspace not found",
            })
            from odap.web.app import app
            self.client = TestClient(app)
            yield

    def test_create_entity_type_and_add_properties(self):
        from odap.biz.core.ontology.design.impl.builder import OntologyBuilder
        builder = OntologyBuilder()

        doc = builder.create_ontology_document(
            name=f"e2e-ontology-{uuid.uuid4().hex[:8]}",
            description="E2E workflow test ontology",
        )
        assert doc is not None
        assert doc.name.startswith("e2e-ontology-")

        data = {
            "entities": [
                {
                    "entity_type": "Unit",
                    "name": "E2E-Unit-1",
                    "properties": {
                        "unit_id": "unit-001",
                        "name": "Alpha Squad",
                        "side": "blue",
                        "unit_type": "infantry",
                    },
                },
            ],
            "relations": [],
        }
        extracted = builder.extract_entities(data)
        assert len(extracted.entities) == 1
        assert extracted.entities[0]["entity_type"] == "Unit"
        assert extracted.entities[0]["properties"]["side"] == "blue"

    def test_create_instance_and_version_management(self):
        from odap.biz.core.ontology.design.impl.builder import OntologyBuilder
        from odap.biz.core.ontology.design.impl.version import VersionManager
        builder = OntologyBuilder()
        version_mgr = VersionManager()

        doc = builder.create_ontology_document(
            name=f"version-test-{uuid.uuid4().hex[:8]}",
            description="Version management test",
        )
        ontology_id = doc.id

        v1 = version_mgr.create_version(
            ontology_id=ontology_id,
            version_number="1.0.0",
            change_summary="Initial version",
        )
        assert v1 is not None
        assert v1.version_number == "1.0.0"

        v2 = version_mgr.create_version(
            ontology_id=ontology_id,
            version_number="2.0.0",
            parent_version_id=v1.version_id,
            change_summary="Added new entity types",
        )
        assert v2 is not None
        assert v2.version_number == "2.0.0"

        versions = version_mgr.list_versions(ontology_id)
        assert len(versions) >= 2

    def test_version_rollback(self):
        from odap.biz.core.ontology.design.impl.builder import OntologyBuilder
        from odap.biz.core.ontology.design.impl.version import VersionManager
        builder = OntologyBuilder()
        version_mgr = VersionManager()

        doc = builder.create_ontology_document(
            name=f"rollback-test-{uuid.uuid4().hex[:8]}",
            description="Rollback test",
        )
        ontology_id = doc.id

        v1 = version_mgr.create_version(
            ontology_id=ontology_id,
            version_number="1.0.0",
            change_summary="First version",
        )
        v2 = version_mgr.create_version(
            ontology_id=ontology_id,
            version_number="2.0.0",
            parent_version_id=v1.version_id,
            change_summary="Second version",
        )

        rollback_v = version_mgr.rollback_version(ontology_id, v1.version_id)
        assert rollback_v is not None
        assert "rollback" in rollback_v.version_number
        assert rollback_v.parent_version == v1.version_id


@skip_if_no_service
@pytest.mark.e2e
class TestOntologyDesignerE2ELive:
    def test_full_ontology_designer_flow(self):
        from odap.web.app import app
        client = TestClient(app)

        create_resp = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "Alpha Squad is a blue infantry unit stationed at Sector-7.",
            },
        )
        assert create_resp.status_code in [200, 201]
        data = create_resp.json()
        assert "ingest_id" in data

        ingest_id = data["ingest_id"]
        status_resp = client.get(f"/api/ontology/ingest/{ingest_id}")
        assert status_resp.status_code in [200, 404]
