"""Tests for ontology API routes exception handling.

AGENTS.md 规则验证：
- 规则 2: 服务层不抛 HTTPException，返回 {"status": "error", "message": "..."}
- 规则 3: 路由层必须 except HTTPException: raise 透传
- 路由层翻译服务层错误为 HTTP 状态码
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create test client with dependency override to bypass JWT auth."""
    from odap.web.app import app
    from odap.infra.security.jwt_auth import get_current_user

    # Override the auth dependency with a mock that returns a valid user
    async def _mock_user():
        return {"user_id": "test-user", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

    app.dependency_overrides[get_current_user] = _mock_user
    with TestClient(app) as c:
        yield c
    # Clean up overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service():
    """Patch the module-level service instance in routes."""
    with patch(
        "odap.biz.core.ontology.ontology_api.api.routes.service"
    ) as svc:
        yield svc


# ---------------------------------------------------------------------------
# Test: HTTPException transparency (AGENTS.md 规则 3)
# ---------------------------------------------------------------------------

class TestHTTPExceptionTransparency:
    """HTTPException from inner code should NOT be swallowed by 500 handler."""

    def test_list_ontologies_http_exception_not_swallowed(self, client, mock_service):
        """HTTPException(403) should pass through, NOT become 500."""
        mock_service.list_ontologies.side_effect = HTTPException(
            status_code=403, detail="Forbidden"
        )
        resp = client.get("/api/ontologies")
        assert resp.status_code == 403

    def test_get_ontology_http_exception_not_swallowed(self, client, mock_service):
        """HTTPException(401) should pass through."""
        mock_service.get_ontology.side_effect = HTTPException(
            status_code=401, detail="Unauthorized"
        )
        resp = client.get("/api/ontologies/test-id")
        assert resp.status_code == 401

    def test_create_ontology_http_exception_not_swallowed(self, client, mock_service):
        """HTTPException(422) should pass through."""
        mock_service.create_ontology.side_effect = HTTPException(
            status_code=422, detail="Validation Error"
        )
        resp = client.post("/api/ontologies", json={"name": "Test"})
        assert resp.status_code == 422

    def test_delete_ontology_http_exception_not_swallowed(self, client, mock_service):
        """HTTPException(403) on delete should pass through."""
        mock_service.delete_ontology.side_effect = HTTPException(
            status_code=403, detail="Forbidden"
        )
        resp = client.delete("/api/ontologies/test-id")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: 404 for non-existent resources
# ---------------------------------------------------------------------------

class TestNotFoundResponses:
    """Service returns error dict -> route translates to 404."""

    def test_get_nonexistent_ontology_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for get_ontology."""
        mock_service.get_ontology.return_value = {
            "status": "error",
            "message": "Not found",
        }
        resp = client.get("/api/ontologies/nonexistent")
        assert resp.status_code == 404
        assert "Not found" in resp.json()["detail"]

    def test_update_nonexistent_ontology_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for update."""
        mock_service.update_ontology.return_value = {
            "status": "error",
            "message": "Not found",
        }
        resp = client.put(
            "/api/ontologies/nonexistent",
            json={"name": "Updated"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_ontology_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for delete."""
        mock_service.delete_ontology.return_value = {
            "status": "error",
            "message": "Not found",
        }
        resp = client.delete("/api/ontologies/nonexistent")
        assert resp.status_code == 404

    def test_delete_nonexistent_object_type_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for delete_object_type."""
        mock_service.delete_object_type.return_value = {
            "status": "error",
            "message": "Not found",
        }
        resp = client.delete("/api/ontologies/object-types/nonexistent")
        assert resp.status_code == 404

    def test_delete_nonexistent_link_type_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for delete_link_type."""
        mock_service.delete_link_type.return_value = {
            "status": "error",
            "message": "Not found",
        }
        resp = client.delete("/api/ontologies/link-types/nonexistent")
        assert resp.status_code == 404

    def test_get_nonexistent_extraction_session_returns_404(self, client, mock_service):
        """Service returns error -> route raises 404 for get_extraction_session."""
        mock_service.get_extraction_session.return_value = {
            "status": "error",
            "message": "Session not found",
        }
        resp = client.get("/api/ontologies/extraction-sessions/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: 400 for error responses from service layer (create/update)
# ---------------------------------------------------------------------------

class TestBadRequestResponses:
    """Service returns error dict -> route translates to 400 for create/update."""

    def test_create_ontology_error_returns_400(self, client, mock_service):
        """Service returns error -> route raises 400 for create_ontology."""
        mock_service.create_ontology.return_value = {
            "status": "error",
            "message": "Name already exists",
        }
        resp = client.post(
            "/api/ontologies",
            json={"name": "Duplicate"},
        )
        assert resp.status_code == 400
        assert "Name already exists" in resp.json()["detail"]

    def test_create_object_type_error_returns_400(self, client, mock_service):
        """Registry returns error -> route raises 400 for create_object_type.

        Note: route uses TypeRegistry (not service) for writes to keep OMS cache
        in sync (see routes.py `_get_type_registry`). Mock the registry, not service.
        """
        with patch(
            "odap.biz.core.ontology.ontology_api.api.routes._get_type_registry"
        ) as mock_get_reg:
            mock_registry = mock_get_reg.return_value
            mock_registry.create_object_type.return_value = {
                "status": "error",
                "message": "Invalid type definition",
            }
            resp = client.post(
                "/api/ontologies/ont-123/object-types",
                json={"name": "BadType"},
            )
            assert resp.status_code == 400
            assert "Invalid type definition" in resp.json()["detail"]

    def test_create_link_type_error_returns_400(self, client, mock_service):
        """Service returns error -> route raises 400 for create_link_type."""
        mock_service.create_link_type.return_value = {
            "status": "error",
            "message": "Source type not found",
        }
        resp = client.post(
            "/api/ontologies/ont-123/link-types",
            json={"name": "BadLink"},
        )
        assert resp.status_code == 400

    def test_commit_schema_version_error_returns_400(self, client, mock_service):
        """Service returns error -> route raises 400 for commit_schema_version."""
        mock_service.commit_schema_version.return_value = {
            "status": "error",
            "message": "No changes to commit",
        }
        resp = client.post(
            "/api/ontologies/ont-123/commit",
            json={"changelog": "test"},
        )
        assert resp.status_code == 400

    def test_save_database_connection_error_returns_400(self, client, mock_service):
        """Service returns error -> route raises 400 for save_database_connection."""
        mock_service.save_database_connection.return_value = {
            "status": "error",
            "message": "Invalid connection config",
        }
        resp = client.post(
            "/api/ontologies/database-connections",
            json={"name": "BadConn"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test: 500 for unexpected exceptions
# ---------------------------------------------------------------------------

class TestInternalServerErrorResponses:
    """Unexpected exceptions should be caught and return 500."""

    def test_list_ontologies_unexpected_error_returns_500(self, client, mock_service):
        """RuntimeError in service -> route catches and returns 500."""
        mock_service.list_ontologies.side_effect = RuntimeError("DB connection lost")
        resp = client.get("/api/ontologies")
        assert resp.status_code == 500
        assert "DB connection lost" in resp.json()["detail"]

    def test_create_ontology_unexpected_error_returns_500(self, client, mock_service):
        """ValueError in service -> route catches and returns 500."""
        mock_service.create_ontology.side_effect = ValueError("Unexpected")
        resp = client.post(
            "/api/ontologies",
            json={"name": "Test"},
        )
        assert resp.status_code == 500

    def test_delete_ontology_unexpected_error_returns_500(self, client, mock_service):
        """RuntimeError on delete -> route catches and returns 500."""
        mock_service.delete_ontology.side_effect = RuntimeError("Disk full")
        resp = client.delete("/api/ontologies/test-id")
        assert resp.status_code == 500

    def test_get_ontology_graph_unexpected_error_returns_500(self, client, mock_service):
        """RuntimeError in get_ontology_graph -> route catches and returns 500."""
        mock_service.get_ontology_graph.side_effect = RuntimeError("Graph error")
        resp = client.get("/api/ontologies/ont-123/graph")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Test: Successful responses
# ---------------------------------------------------------------------------

class TestSuccessfulResponses:
    """Successful service returns should pass through as 200."""

    def test_list_ontologies_success(self, client, mock_service):
        """Successful list returns 200."""
        mock_service.list_ontologies.return_value = [
            {"ontology_id": "ont-1", "name": "Test"},
        ]
        resp = client.get("/api/ontologies")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_ontology_success(self, client, mock_service):
        """Successful creation returns 200."""
        mock_service.create_ontology.return_value = {
            "ontology_id": "test-123",
            "name": "Test",
        }
        resp = client.post(
            "/api/ontologies",
            json={"name": "Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ontology_id"] == "test-123"

    def test_get_ontology_success(self, client, mock_service):
        """Successful get returns 200."""
        mock_service.get_ontology.return_value = {
            "ontology_id": "ont-1",
            "name": "Test",
        }
        resp = client.get("/api/ontologies/ont-1")
        assert resp.status_code == 200

    def test_delete_ontology_success(self, client, mock_service):
        """Successful delete returns 200."""
        mock_service.delete_ontology.return_value = {
            "status": "ok",
            "message": "Deleted",
        }
        resp = client.delete("/api/ontologies/ont-1")
        assert resp.status_code == 200

    def test_list_schema_versions_success(self, client, mock_service):
        """Successful list versions returns 200."""
        mock_service.list_schema_versions.return_value = [
            {"version_id": "v1", "version_number": "0.1.0"},
        ]
        resp = client.get("/api/ontologies/ont-1/versions")
        assert resp.status_code == 200

    def test_get_ontology_graph_success(self, client, mock_service):
        """Successful graph data returns 200."""
        mock_service.get_ontology_graph.return_value = {
            "nodes": [],
            "edges": [],
        }
        resp = client.get("/api/ontologies/ont-1/graph")
        assert resp.status_code == 200
