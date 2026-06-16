"""End-to-end test fixtures.

E2E tests exercise full user workflows through the API.
Fixtures here provide:
- Authenticated API clients
- Test data setup/teardown
- Workflow helpers
"""

import os
import sys
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def api_base_url():
    """Return the backend API base URL for E2E tests."""
    return os.environ.get("E2E_API_URL", "http://localhost:8000")


@pytest.fixture
def e2e_auth_token(api_base_url):
    """Obtain a JWT token for E2E tests by logging in.

    Requires the backend to be running and the default admin user to exist.
    """
    import urllib.request
    import json

    login_url = f"{api_base_url}/api/auth/login"
    data = json.dumps({"username": "admin", "password": "admin123"}).encode()
    req = urllib.request.Request(
        login_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return body.get("access_token")
    except Exception:
        pytest.skip("E2E backend not available or login failed")
