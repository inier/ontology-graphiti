"""Integration test fixtures.

Integration tests require external services (Neo4j, OPA, etc.).
Fixtures here provide:
- Service health checks
- Shared client instances
- Test data seeding helpers
"""

import os
import sys
import pytest

# apps/api/tests/integration/conftest.py
#   3 dirname -> apps/api/   (使 `import odap` 可用)
#   5 dirname -> monorepo root
_this = os.path.abspath(__file__)
_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this)))  # apps/api/
_root = os.path.dirname(os.path.dirname(_api_dir))                   # monorepo root
for _p in (_api_dir, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _is_service_available(url: str, timeout: float = 2.0) -> bool:
    """Check if a service is reachable."""
    import urllib.request
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


@pytest.fixture
def neo4j_available():
    """Skip test if Neo4j is not available."""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    host = uri.replace("bolt://", "").split(":")[0]
    if not _is_service_available(f"http://{host}:7474"):
        pytest.skip("Neo4j not available")
    return True


@pytest.fixture
def opa_available():
    """Skip test if OPA is not available."""
    opa_url = os.environ.get("OPA_URL", "http://localhost:8181")
    if not _is_service_available(f"{opa_url}/health"):
        pytest.skip("OPA not available")
    return True


@pytest.fixture
def backend_available():
    """Skip test if the backend API is not available."""
    if not _is_service_available("http://localhost:8000/health"):
        pytest.skip("Backend API not available")
    return True
