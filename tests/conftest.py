"""
测试配置和 fixtures
"""

import sys
import os
import pytest
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def test_client():
    """提供 FastAPI TestClient"""
    from app.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client():
    """提供异步 HTTP 客户端"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def unique_suffix():
    """生成唯一后缀用于测试"""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def sample_workspace_data(unique_suffix):
    """示例工作空间数据"""
    return {
        "name": f"测试工作空间-{unique_suffix}",
        "description": "用于集成测试的工作空间"
    }


@pytest.fixture
def sample_scenario_data(unique_suffix):
    """示例场景数据"""
    return {
        "name": f"测试场景-{unique_suffix}",
        "description": "用于集成测试的场景"
    }


@pytest.fixture
def sample_role_data(unique_suffix):
    """示例角色数据"""
    return {
        "name": f"测试角色-{unique_suffix}",
        "description": "用于集成测试的角色",
        "role_type": "member",
        "permissions": ["workspace:read", "scenario:read"]
    }


@pytest.fixture
def sample_qa_data():
    """示例问答数据"""
    return {
        "question": "有哪些雷达目标？",
        "user_id": "test_user"
    }


@pytest.fixture
def sample_manual_data():
    """示例手动录入数据"""
    return {
        "data": {
            "entities": [
                {
                    "entity_id": f"test-entity-{uuid.uuid4().hex[:8]}",
                    "name": "测试单位A",
                    "entity_type": "unit",
                    "basic_properties": {"side": "red", "strength": 100}
                }
            ],
            "events": [
                {
                    "event_id": f"test-event-{uuid.uuid4().hex[:8]}",
                    "event_type": "deployment",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "description": "测试部队部署",
                    "participants": [f"test-entity-{uuid.uuid4().hex[:8]}"]
                }
            ]
        }
    }


@pytest.fixture
def sample_feedback_data():
    """示例反馈数据"""
    return {
        "rating": 4,
        "feedback": {"useful": True, "comment": "回答很准确"},
        "user_id": "test_user"
    }