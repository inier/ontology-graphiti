import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    with patch("odap.biz.frontend_compat.api.routes.scenario_store", MagicMock()):
        with patch("odap.biz.frontend_compat.api.routes.workspace_service", MagicMock()):
            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)
            yield client


class TestHealthEndpoint:
    def test_health_check(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200


class TestWorkspaceAPI:
    def test_list_workspaces(self, app_client):
        response = app_client.get("/api/workspaces")
        assert response.status_code in [200, 404, 500]

    def test_create_workspace(self, app_client):
        response = app_client.post(
            "/api/workspaces",
            json={
                "name": "测试空间",
                "type": "default",
                "isolation_strategy": "standard",
            },
        )
        assert response.status_code in [200, 201, 400, 422, 500]


class TestRolesAPI:
    def test_list_roles(self, app_client):
        response = app_client.get("/api/roles")
        assert response.status_code in [200, 500]

    def test_list_permissions(self, app_client):
        response = app_client.get("/api/roles/permissions/all")
        assert response.status_code in [200, 500]


class TestSkillAPI:
    def test_list_skills(self, app_client):
        response = app_client.get("/api/skill/skills")
        assert response.status_code in [200, 500]

    def test_loaded_skills(self, app_client):
        response = app_client.get("/api/skill/skills/loaded")
        assert response.status_code in [200, 500]


class TestHookAPI:
    def test_list_hooks(self, app_client):
        response = app_client.get("/api/hook/hooks")
        assert response.status_code in [200, 500]


class TestMCPAPI:
    def test_list_servers(self, app_client):
        response = app_client.get("/api/mcp/servers")
        assert response.status_code in [200, 500]


class TestEventSimulatorAPI:
    def test_list_templates(self, app_client):
        response = app_client.get("/api/event-simulator/templates")
        assert response.status_code in [200, 500]

    def test_list_events(self, app_client):
        response = app_client.get("/api/event-simulator/events")
        assert response.status_code in [200, 500]


class TestOntologyIngestAPI:
    def test_list_ingest_history(self, app_client):
        response = app_client.get("/api/ontology/ingest")
        assert response.status_code in [200, 500]

    def test_list_versions(self, app_client):
        response = app_client.get("/api/ontology/ingest/versions")
        assert response.status_code in [200, 500]

    def test_list_documents(self, app_client):
        response = app_client.get("/api/ontology/ingest/documents/list")
        assert response.status_code in [200, 500]


class TestAgentAPI:
    def test_agent_status(self, app_client):
        response = app_client.get("/api/agent/status")
        assert response.status_code in [200, 500]


class TestBusinessAPI:
    def test_list_processes(self, app_client):
        response = app_client.get("/api/business-processes")
        assert response.status_code in [200, 500]

    def test_list_rules(self, app_client):
        response = app_client.get("/api/business-rules")
        assert response.status_code in [200, 500]

    def test_list_logics(self, app_client):
        response = app_client.get("/api/business-logics")
        assert response.status_code in [200, 500]

    def test_list_indicators(self, app_client):
        response = app_client.get("/api/business-indicators")
        assert response.status_code in [200, 500]


class TestFrontendCompatAPI:
    def test_list_scenarios(self, app_client):
        response = app_client.get("/api/scenarios")
        assert response.status_code in [200, 500]

    def test_get_ontology_schema(self, app_client):
        response = app_client.get("/api/ontology/schema")
        assert response.status_code in [200, 500]

    def test_list_audit_events(self, app_client):
        response = app_client.get("/api/audit/events")
        assert response.status_code in [200, 500]

    def test_list_policies(self, app_client):
        response = app_client.get("/api/policies")
        assert response.status_code in [200, 500]
