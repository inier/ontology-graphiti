import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# C3 fix: 测试环境注入 JWT_SECRET，使 app.py lifespan 的 strict 校验通过。
# 仅当未显式设置时注入，允许单个测试用 monkeypatch 覆盖为非法值以测试 fail-fast。
_TEST_JWT_SECRET = "test_secret_key_for_unit_tests_padded_to_32bytes"  # 43 bytes
if not os.environ.get("JWT_SECRET"):
    os.environ["JWT_SECRET"] = _TEST_JWT_SECRET


@pytest.fixture
def mock_sqlite():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone = MagicMock(return_value=None)
    cursor.fetchall = MagicMock(return_value=[])
    cursor.execute = MagicMock()
    cursor.rowcount = 1
    conn.cursor = MagicMock(return_value=cursor)
    conn.execute = MagicMock(return_value=cursor)
    conn.commit = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.fixture
def temp_db(tmp_path):
    import sqlite3
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn, db_path
    conn.close()


@pytest.fixture
def tool_registry():
    from odap.biz.platform.tool_registry.registry import ToolRegistry
    return ToolRegistry()


@pytest.fixture
def skill_registry():
    from odap.tools.base import get_registry_v2
    return get_registry_v2()


@pytest.fixture
def audit_logger():
    from odap.infra.security.audit_logger import AuditLogger
    return AuditLogger()
