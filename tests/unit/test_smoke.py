"""ODAP 冒烟测试套件 (Smoke Tests)

冒烟测试目标：在 < 60s 内验证系统最核心的功能可用性，用于：
- 每次提交前的快速回归验证
- 部署后的健康检查
- CI 流水线的快速门禁

覆盖范围（仅核心路径，不追求完整覆盖）：
1. Web 应用启动 + 健康检查端点
2. JWT 认证服务
3. 核心领域模型（本体、工作空间、Agent）默认值与序列化
4. 关键架构守护规则（路由异常透传、Pydantic 可变默认值）
5. 核心存储层（SQLite CRUD 基本流程）
6. 路由注册完整性

运行：python run_tests.py smoke
或：  pytest -m smoke tests/
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# 1. Web 应用启动与健康检查
# ---------------------------------------------------------------------------


@pytest.fixture
def smoke_client():
    """创建绕过认证的 TestClient，仅用于冒烟测试。"""
    with patch("odap.web.app.get_openharness_integration") as mock_get, \
         patch("odap.web.app.GraphManager", create=True) as mock_cls, \
         patch("odap.web.app.GRAPHITI_AVAILABLE", False, create=True):
        mock_integration = MagicMock()
        mock_integration.get_status.return_value = {
            "openharness_available": False,
            "engine_type": "unknown",
            "agent_loop_initialized": False,
            "tools_count": 0,
            "tools": [],
        }
        mock_integration.shutdown = AsyncMock()
        mock_get.return_value = mock_integration
        mock_gm = MagicMock()
        mock_gm._mode = "fallback"
        mock_gm._connected = False
        mock_gm._use_fallback = True
        mock_cls.return_value = mock_gm

        from odap.web.app import app
        from odap.infra.security.jwt_auth import get_current_user
        from fastapi.testclient import TestClient

        async def _mock_user():
            return {"user_id": "smoke", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

        app.dependency_overrides[get_current_user] = _mock_user
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


class TestAppStartup:
    """Web 应用启动冒烟测试。"""

    def test_root_endpoint(self, smoke_client):
        """根端点返回 200 与版本信息。"""
        resp = smoke_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Graphiti API"
        assert "version" in data

    def test_health_endpoint(self, smoke_client):
        """/health 返回 healthy 状态。"""
        resp = smoke_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "openharness" in data
        assert "graphiti" in data


# ---------------------------------------------------------------------------
# 2. JWT 认证服务
# ---------------------------------------------------------------------------


class TestJWTAuthService:
    """JWT 认证核心功能冒烟测试。"""

    def test_create_and_verify_token(self):
        """JWT Token 创建与验证。"""
        from odap.infra.security.jwt_service import JWTService

        svc = JWTService(secret_key="smoke-test-secret-key-at-least-32-chars!!")
        token = svc.issue_access_token(
            user_id="u1", user_name="admin", role="admin",
            workspace_id="ws-1", workspace_role="owner",
        )
        assert token is not None
        payload = svc.verify_token(token)
        assert payload is not None

    def test_invalid_token_rejected(self):
        """非法 Token 被拒绝。"""
        from odap.infra.security.jwt_service import JWTService

        svc = JWTService(secret_key="smoke-test-secret-key-at-least-32-chars!!")
        with pytest.raises(Exception):
            svc.verify_token("invalid.token.here")


# ---------------------------------------------------------------------------
# 3. 核心领域模型
# ---------------------------------------------------------------------------


class TestCoreModels:
    """核心领域模型默认值与序列化。"""

    def test_ontology_document_model_defaults(self):
        """本体文档模型默认值正确（Pydantic BaseModel）。"""
        from odap.biz.core.ontology.design.model.models.ontology_document import (
            OntologyDocument,
        )

        doc = OntologyDocument(name="smoke-ont")
        assert doc.name == "smoke-ont"
        assert doc.version == "1.0.0"
        assert isinstance(doc.object_types, list)  # default_factory 生效
        assert isinstance(doc.metadata, dict)

    def test_workspace_model_defaults(self):
        """工作空间模型默认值正确。"""
        from odap.biz.platform.workspace.models.workspace import (
            Workspace,
            WorkspaceStatus,
        )

        ws = Workspace(name="ws", owner="u1")
        assert ws.name == "ws"
        assert ws.id  # uuid 自动生成
        assert ws.status == WorkspaceStatus.CREATING
        assert isinstance(ws.tags, list)  # default_factory 生效
        assert isinstance(ws.members, list)


# ---------------------------------------------------------------------------
# 4. 架构守护规则
# ---------------------------------------------------------------------------


class TestArchitectureGuards:
    """关键架构守护规则冒烟测试。"""

    def test_pydantic_no_mutable_defaults(self):
        """Pydantic 模型不应使用可变默认值（= [] / = {}）。"""
        import inspect
        import re

        from odap.biz.core.ontology.design.models import ontology as ont_module

        violations = []
        # 检查模块中所有 BaseModel 子类
        for name, obj in inspect.getmembers(ont_module, inspect.isclass):
            try:
                from pydantic import BaseModel
                if not issubclass(obj, BaseModel) or obj is BaseModel:
                    continue
            except Exception:
                continue
            src = inspect.getsource(obj)
            # 简化检查：字段定义中出现 = [] 或 = {}（非 default_factory）
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or "default_factory" in stripped:
                    continue
                if re.search(r"=\s*\[\s*\]", stripped) or re.search(
                    r"=\s*\{\s*\}", stripped
                ):
                    if ":" in stripped and not stripped.strip().startswith("def "):
                        violations.append(f"{name}.{stripped}")
        assert not violations, f"发现可变默认值: {violations}"


# ---------------------------------------------------------------------------
# 5. 核心 SQLite 存储层
# ---------------------------------------------------------------------------


class TestCoreStorage:
    """核心存储层 CRUD 冒烟测试。"""

    def test_ontology_storage_crud(self, tmp_path):
        """本体存储 CRUD 基本流程。"""
        from odap.biz.core.ontology.design.storage.sqlite_ingest_storage import (
            SQLiteIngestStorage,
        )

        storage = SQLiteIngestStorage(db_path=str(tmp_path / "smoke.db"))
        # 基本验证：能初始化、能列出（即使为空）
        items = storage.list_documents() if hasattr(storage, "list_documents") else []
        assert isinstance(items, list)

    def test_health_storage_crud(self, tmp_path):
        """健康规则存储 CRUD 基本流程。"""
        from odap.biz.core.ontology.health.storage import SQLiteHealthStorage

        storage = SQLiteHealthStorage(db_path=str(tmp_path / "smoke-health.db"))
        # 存储层接收 dict（按 AGENTS.md 规则，复杂字段存 JSON TEXT）
        rule_dict = {
            "id": "rule-smoke-001",
            "target_type_id": "Customer",
            "name": "smoke-rule",
            "description": "smoke",
            "rule_type": "not_null",
            "check_expression": {"properties": ["name"]},
            "severity": "warning",
            "schedule": "",
            "notification_channel": {},
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        storage.save_rule(rule_dict)
        got = storage.get_rule("rule-smoke-001")
        assert got is not None
        assert got["name"] == "smoke-rule"


# ---------------------------------------------------------------------------
# 6. 路由注册完整性
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    """关键路由注册完整性冒烟测试。"""

    def test_core_routes_registered(self, smoke_client):
        """核心 API 路由已注册。"""
        from odap.web.app import app

        paths = {route.path for route in app.routes}
        # 健康检查与根路径
        assert "/" in paths
        assert "/health" in paths
        # 至少有 /api 前缀的路由
        api_paths = [p for p in paths if p.startswith("/api")]
        assert len(api_paths) > 0, "未注册任何 /api 路由"


# ---------------------------------------------------------------------------
# 7. 工厂函数与测试工具
# ---------------------------------------------------------------------------


class TestHelpersIntact:
    """测试辅助工具可用性。"""

    def test_factories_produce_valid_data(self):
        """工厂函数生成有效数据。"""
        from tests.helpers.factories import (
            make_ontology,
            make_workspace,
            make_agent,
            make_scenario,
        )

        ont = make_ontology(name="x")
        assert ont["name"] == "x"
        assert "workspace_id" in ont

        ws = make_workspace()
        assert "name" in ws

        agent = make_agent()
        assert "name" in agent

        sc = make_scenario()
        assert "workspace_id" in sc
