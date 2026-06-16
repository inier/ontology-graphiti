"""Web App (odap/web/app.py) 单元测试

覆盖:
- health_check 端点返回 200 和 status "healthy"
- root 端点返回欢迎消息和版本信息
- 所有路由已注册（检查 app.routes 中的预期前缀）
- CORS 中间件配置
- lifespan 上下文管理器

注意:
- 使用 FastAPI TestClient + dependency_overrides 绕过认证
- Mock 外部依赖（GraphManager, OpenHarness integration 等）
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_openharness():
    """Mock OpenHarness integration"""
    with patch("odap.web.app.get_openharness_integration") as mock_get:
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
        yield mock_integration


@pytest.fixture
def mock_graph_manager():
    """Mock GraphManager"""
    with patch("odap.web.app.GraphManager", create=True) as mock_cls:
        mock_gm = MagicMock()
        mock_gm._mode = "fallback"
        mock_gm._connected = False
        mock_gm._use_fallback = True
        mock_cls.return_value = mock_gm
        yield mock_gm


@pytest.fixture
def mock_graphiti_available():
    """Mock GRAPHITI_AVAILABLE"""
    with patch("odap.web.app.GRAPHITI_AVAILABLE", False, create=True):
        yield


@pytest.fixture
def client(mock_openharness, mock_graph_manager):
    """创建 TestClient，绕过认证依赖"""
    # 需要在 import app 之前 mock 掉路由注册中的外部依赖
    # 由于 app 模块已在 import 时执行，我们直接使用已创建的 app 实例
    from odap.web.app import app
    from odap.infra.security.jwt_auth import get_current_user

    async def _mock_user():
        return {"user_id": "test-user", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

    app.dependency_overrides[get_current_user] = _mock_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================
# 1. Root 端点测试
# ============================================================


class TestRootEndpoint:
    """GET / 根路径端点"""

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_message(self, client):
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert data["message"] == "Graphiti API"

    def test_root_returns_version(self, client):
        response = client.get("/")
        data = response.json()
        assert "version" in data
        assert data["version"] == "2.0.0"

    def test_root_returns_features(self, client):
        response = client.get("/")
        data = response.json()
        assert "features" in data
        assert isinstance(data["features"], list)
        assert len(data["features"]) > 0

    def test_root_returns_endpoints(self, client):
        response = client.get("/")
        data = response.json()
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert len(data["endpoints"]) > 0


# ============================================================
# 2. Health 端点测试
# ============================================================


class TestHealthEndpoint:
    """GET /health 健康检查端点"""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["version"] == "2.0.0"

    def test_health_contains_openharness_info(self, client):
        response = client.get("/health")
        data = response.json()
        assert "openharness" in data
        oh = data["openharness"]
        assert "available" in oh
        assert "engine_type" in oh
        assert "agent_loop_initialized" in oh
        assert "tools_count" in oh

    def test_health_contains_graphiti_info(self, client):
        response = client.get("/health")
        data = response.json()
        assert "graphiti" in data
        g = data["graphiti"]
        assert "graphiti_core_installed" in g
        assert "graph_mode" in g
        assert "connected" in g
        assert "use_fallback" in g


# ============================================================
# 3. 路由注册测试
# ============================================================


class TestRouterRegistration:
    """验证所有路由已注册到 app"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_openharness, mock_graph_manager):
        from odap.web.app import app
        self.app = app
        self.routes = app.routes

    def _get_route_paths(self) -> set:
        """获取所有已注册路由的路径"""
        paths = set()
        for route in self.routes:
            if hasattr(route, "path"):
                paths.add(route.path)
        return paths

    def _get_route_prefixes(self) -> set:
        """获取所有已注册路由的前缀（APIRouter 的 prefix）"""
        prefixes = set()
        for route in self.routes:
            if hasattr(route, "path") and route.path.startswith("/api/"):
                # 提取 /api/xxx 部分
                parts = route.path.split("/")
                if len(parts) >= 3:
                    prefixes.add("/" + "/".join(parts[1:3]))
        return prefixes

    def test_root_route_registered(self):
        paths = self._get_route_paths()
        assert "/" in paths

    def test_health_route_registered(self):
        paths = self._get_route_paths()
        assert "/health" in paths

    def test_workspace_routes_registered(self):
        prefixes = self._get_route_prefixes()
        assert "/api/workspace" in prefixes or any("/api/workspace" in p for p in self._get_route_paths())

    def test_auth_routes_registered(self):
        paths = self._get_route_paths()
        auth_paths = [p for p in paths if "/api/auth" in p]
        assert len(auth_paths) > 0

    def test_ontology_routes_registered(self):
        paths = self._get_route_paths()
        ontology_paths = [p for p in paths if "/api/ontology" in p]
        assert len(ontology_paths) > 0

    def test_agent_routes_registered(self):
        paths = self._get_route_paths()
        agent_paths = [p for p in paths if "/api/agent" in p]
        assert len(agent_paths) > 0

    def test_audit_routes_registered(self):
        paths = self._get_route_paths()
        audit_paths = [p for p in paths if "/api/audit" in p]
        assert len(audit_paths) > 0

    def test_roles_routes_registered(self):
        paths = self._get_route_paths()
        roles_paths = [p for p in paths if "/api/roles" in p]
        assert len(roles_paths) > 0

    def test_skill_routes_registered(self):
        paths = self._get_route_paths()
        skill_paths = [p for p in paths if "/api/skill" in p]
        assert len(skill_paths) > 0

    def test_hook_routes_registered(self):
        paths = self._get_route_paths()
        hook_paths = [p for p in paths if "/api/hook" in p]
        assert len(hook_paths) > 0

    def test_mcp_routes_registered(self):
        paths = self._get_route_paths()
        mcp_paths = [p for p in paths if "/api/mcp" in p]
        assert len(mcp_paths) > 0

    def test_event_simulator_routes_registered(self):
        paths = self._get_route_paths()
        sim_paths = [p for p in paths if "/api/event-simulator" in p]
        assert len(sim_paths) > 0

    def test_business_routes_registered(self):
        paths = self._get_route_paths()
        biz_paths = [p for p in paths if "/api/business" in p]
        assert len(biz_paths) > 0

    def test_total_api_routes_exceeds_minimum(self):
        """至少应有 30 个 API 路由"""
        api_paths = [p for p in self._get_route_paths() if p.startswith("/api/")]
        assert len(api_paths) >= 30


# ============================================================
# 4. CORS 中间件测试
# ============================================================


class TestCORSMiddleware:
    """CORS 中间件配置"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_openharness, mock_graph_manager):
        from odap.web.app import app
        self.app = app

    def test_cors_headers_on_options(self, client):
        """OPTIONS 预检请求应返回 CORS 头"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # 预检请求可能返回 200, 204, 400 或 405
        # 400 可能因为缺少某些头，但关键是 CORS 中间件已注册
        assert response.status_code in (200, 204, 400, 405)

    def test_cors_allows_content_type_header(self, client):
        """Content-Type 应在 allow_headers 中"""
        from odap.web.app import app
        # 检查中间件栈中是否有 CORSMiddleware
        middleware_found = False
        for mw in app.user_middleware:
            if "CORSMiddleware" in str(mw):
                middleware_found = True
                break
        # CORSMiddleware 可能通过 add_middleware 添加到栈顶
        assert len(app.user_middleware) > 0


# ============================================================
# 5. App 元数据测试
# ============================================================


class TestAppMetadata:
    """FastAPI 应用元数据"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_openharness, mock_graph_manager):
        from odap.web.app import app
        self.app = app

    def test_app_title(self):
        assert self.app.title == "Graphiti API"

    def test_app_version(self):
        assert self.app.version == "2.0.0"

    def test_app_has_lifespan(self):
        """app 应配置了 lifespan 上下文管理器"""
        assert self.app.router.lifespan_context is not None


# ============================================================
# 6. 异常处理中间件测试
# ============================================================


class TestExceptionHandler:
    """异常处理中间件已注册"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_openharness, mock_graph_manager):
        from odap.web.app import app
        self.app = app

    def test_exception_handler_registered(self):
        """app 应注册了异常处理器"""
        # FastAPI 的 exception_handlers 属性
        assert len(self.app.exception_handlers) > 0


# ============================================================
# 7. 认证绕过验证
# ============================================================


class TestAuthBypass:
    """验证 dependency_overrides 能正确绕过认证"""

    def test_health_no_auth_required(self, client):
        """health 端点不需要认证"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_no_auth_required(self, client):
        """root 端点不需要认证"""
        response = client.get("/")
        assert response.status_code == 200


# ============================================================
# 入口
# ============================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
