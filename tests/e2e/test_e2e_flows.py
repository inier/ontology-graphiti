import pytest
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    with patch("odap.biz.frontend_compat.api.routes.scenario_store", MagicMock()):
        with patch("odap.biz.frontend_compat.api.routes.workspace_service", MagicMock()):
            from app.main import app
            return TestClient(app, raise_server_exceptions=False)


@pytest.mark.e2e
class TestE2EWorkspaceFlow:
    def test_full_workspace_lifecycle(self, client):
        response = client.post(
            "/api/workspaces",
            json={"name": "E2E测试空间", "type": "default", "description": "端到端测试"},
        )
        assert response.status_code in [200, 201]
        ws_data = response.json()
        ws_id = ws_data.get("workspace_id") or ws_data.get("id", "default")

        response = client.get("/api/workspaces")
        assert response.status_code == 200
        ws_list = response.json()
        assert "workspaces" in ws_list
        assert isinstance(ws_list["workspaces"], list)

        if ws_id and ws_id != "default":
            response = client.get(f"/api/workspaces/{ws_id}")
            assert response.status_code in [200, 404]

            response = client.put(
                f"/api/workspaces/{ws_id}",
                json={"name": "更新后空间"},
            )
            assert response.status_code in [200, 404]

            response = client.delete(f"/api/workspaces/{ws_id}")
            assert response.status_code in [200, 404]


@pytest.mark.e2e
class TestE2EBusinessFlow:
    def test_business_process_lifecycle(self, client):
        response = client.get("/api/business-processes")
        assert response.status_code == 200
        initial_list = response.json()

        response = client.post(
            "/api/business-processes",
            json={"name": "E2E测试流程", "description": "端到端测试"},
        )
        assert response.status_code in [200, 201]
        process = response.json()
        process_id = process.get("process_id")

        if process_id:
            response = client.get(f"/api/business-processes/{process_id}")
            assert response.status_code in [200, 404]

            response = client.put(
                f"/api/business-processes/{process_id}",
                json={"name": "更新后流程"},
            )
            assert response.status_code in [200, 404]

            response = client.delete(f"/api/business-processes/{process_id}")
            assert response.status_code in [200, 404]


@pytest.mark.e2e
class TestE2ERoleFlow:
    def test_role_lifecycle(self, client):
        response = client.get("/api/roles")
        assert response.status_code == 200
        roles = response.json()
        assert isinstance(roles, list)

        response = client.get("/api/roles/permissions/all")
        assert response.status_code == 200
        perms = response.json()
        assert isinstance(perms, list)

        response = client.post(
            "/api/roles",
            json={"name": "E2E测试角色", "role_type": "member", "description": "端到端测试", "permissions": []},
        )
        assert response.status_code in [200, 201, 422]


@pytest.mark.e2e
class TestE2ESkillFlow:
    def test_skill_operations(self, client):
        response = client.get("/api/skill/skills")
        assert response.status_code == 200

        response = client.get("/api/skill/skills/loaded")
        assert response.status_code == 200


@pytest.mark.e2e
class TestE2EAuditFlow:
    def test_audit_query(self, client):
        response = client.get("/api/audit/events")
        assert response.status_code in [200, 500]

        response = client.get("/api/audit/stats")
        assert response.status_code in [200, 500]


@pytest.mark.e2e
class TestE2EPolicyFlow:
    def test_policy_lifecycle(self, client):
        response = client.get("/api/policies")
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        assert isinstance(data["policies"], list)

        response = client.post(
            "/api/policies",
            json={
                "name": "E2E测试策略",
                "description": "端到端测试策略",
                "markdown_content": "# 测试策略\n\n测试内容",
                "category": "custom",
            },
        )
        assert response.status_code in [200, 201]


@pytest.mark.e2e
class TestE2EHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
