"""Unit test fixtures and helpers.

Extends the root conftest.py with unit-test-specific utilities:
- Authenticated FastAPI TestClient
- SQLite storage test base helpers
- Common model factories
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

# apps/api/tests/unit/conftest.py
#   3 dirname -> apps/api/   (使 `import odap` 可用)
#   5 dirname -> monorepo root
_this = os.path.abspath(__file__)
_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this)))  # apps/api/
_root = os.path.dirname(os.path.dirname(_api_dir))                   # monorepo root
for _p in (_api_dir, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Authenticated TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client():
    """FastAPI TestClient with JWT auth bypassed.

    Yields a TestClient whose ``get_current_user`` dependency returns
    a mock admin user.  Clean up dependency_overrides after the test.
    """
    from odap.web.app import app
    from odap.infra.security.jwt_auth import get_current_user

    async def _mock_admin_user():
        return {
            "user_id": "test-admin",
            "role": "admin",
            "ws_id": "ws-test",
            "ws_role": "owner",
        }

    app.dependency_overrides[get_current_user] = _mock_admin_user
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client_reader():
    """FastAPI TestClient with a read-only (member) user."""
    from odap.web.app import app
    from odap.infra.security.jwt_auth import get_current_user

    async def _mock_reader_user():
        return {
            "user_id": "test-reader",
            "role": "member",
            "ws_id": "ws-test",
            "ws_role": "reader",
        }

    app.dependency_overrides[get_current_user] = _mock_reader_user
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# SQLite storage helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary SQLite database file path.

    Use this when you need a db_path string (not a connection) to pass
    to a Storage constructor.
    """
    return str(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Service mock helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_response():
    """Return a factory that builds mock LLM response dicts."""
    def _factory(text: str = "mock response", **overrides):
        resp = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        resp.update(overrides)
        return resp

    return _factory


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def async_mock():
    """Shortcut to create an AsyncMock."""
    return AsyncMock()
