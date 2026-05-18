import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def mock_mongodb():
    collection = MagicMock()
    collection.find_one = MagicMock(return_value=None)
    collection.find = MagicMock(return_value=[])
    collection.insert_one = MagicMock(return_value=MagicMock(inserted_id="test-id"))
    collection.update_one = MagicMock(return_value=MagicMock(modified_count=1))
    collection.delete_one = MagicMock(return_value=MagicMock(deleted_count=1))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    client = MagicMock()
    client.__getitem__ = MagicMock(return_value=db)
    return client


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
    from odap.biz.tool_registry.registry import ToolRegistry
    return ToolRegistry()


@pytest.fixture
def skill_registry():
    from odap.tools.base_v2 import get_registry_v2
    return get_registry_v2()


@pytest.fixture
def audit_logger():
    from odap.infra.security.audit_logger import AuditLogger
    return AuditLogger()
