"""FastAPI TestClient helpers for route-level testing.

Provides:
- ``create_auth_client``: Create a TestClient with auth dependency overridden
- ``make_authenticated_request``: Shorthand for common HTTP methods with auth
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_auth_client(
    user_id: str = "test-admin",
    role: str = "admin",
    ws_id: str = "ws-test",
    ws_role: str = "owner",
):
    """Create a FastAPI TestClient with JWT auth bypassed.

    Returns ``(client, cleanup)`` where ``cleanup`` must be called after
    the test to remove dependency overrides.

    Usage::

        client, cleanup = create_auth_client()
        try:
            resp = client.get("/api/ontologies")
            assert resp.status_code == 200
        finally:
            cleanup()

    Or as a fixture::

        @pytest.fixture
        def auth_client():
            client, cleanup = create_auth_client()
            yield client
            cleanup()
    """
    from odap.web.app import app
    from odap.infra.security.jwt_auth import get_current_user
    from fastapi.testclient import TestClient

    async def _mock_user():
        return {
            "user_id": user_id,
            "role": role,
            "ws_id": ws_id,
            "ws_role": ws_role,
        }

    app.dependency_overrides[get_current_user] = _mock_user
    client = TestClient(app)

    def cleanup():
        app.dependency_overrides.clear()

    return client, cleanup


def patch_service(module_path: str, attr_name: str = "service"):
    """Patch a module-level service instance for route testing.

    Returns a context manager that patches the service.

    Usage::

        with patch_service("odap.biz.core.ontology.ontology_api.api.routes") as mock_svc:
            mock_svc.list_ontologies.return_value = {...}
            resp = client.get("/api/ontologies")
    """
    from unittest.mock import patch

    target = f"{module_path}.{attr_name}"
    return patch(target)
