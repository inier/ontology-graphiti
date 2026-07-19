"""配置管理路由测试"""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端（注入 mock JWT user，模拟认证通过）"""
    os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
    from fastapi import FastAPI
    from odap.biz.platform.config.api.routes import router
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(router)

    # 模拟 JWT 认证通过（参考 test_agent_api_routes.py 模式）
    # 写操作路由（update_configs/rollback/import_configs）依赖
    # get_current_user 提取操作者身份，这里注入 mock admin user
    async def _mock_user():
        return {"sub": "test-user", "name": "Test User", "role": "admin"}

    app.dependency_overrides[get_current_user] = _mock_user

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestConfigRoutes:
    """配置管理路由测试"""

    def test_get_all_configs(self, client):
        """测试获取所有配置"""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) >= 8

    def test_get_configs_by_category(self, client):
        """测试按类别获取配置"""
        resp = client.get("/api/config/llm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "llm"

    def test_get_configs_unknown_category(self, client):
        """测试获取未知类别"""
        resp = client.get("/api/config/unknown")
        assert resp.status_code == 404

    def test_update_configs(self, client):
        """测试批量更新配置"""
        resp = client.put("/api/config", json={
            "items": [{"key": "llm.model", "value": "gpt-4o-test"}],
            "test_connection": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["saved_count"] == 1

    def test_update_configs_unknown_key(self, client):
        """测试更新未知 key"""
        resp = client.put("/api/config", json={
            "items": [{"key": "nonexistent.key", "value": "test"}],
            "test_connection": False,
        })
        assert resp.status_code == 400

    def test_update_configs_empty_items(self, client):
        """测试空 items 更新"""
        resp = client.put("/api/config", json={
            "items": [],
            "test_connection": False,
        })
        assert resp.status_code == 200

    def test_get_config_status(self, client):
        """测试获取配置状态总览"""
        resp = client.get("/api/config/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "statuses" in data

    def test_get_config_history(self, client):
        """测试获取变更历史"""
        # 先创建一条变更
        client.put("/api/config", json={
            "items": [{"key": "llm.model", "value": "gpt-4o-history-test"}],
            "test_connection": False,
        })
        resp = client.get("/api/config/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "revisions" in data
        assert "total" in data

    def test_get_config_history_with_params(self, client):
        """测试带参数获取变更历史"""
        resp = client.get("/api/config/history?limit=10&offset=0")
        assert resp.status_code == 200

    def test_rollback_config(self, client):
        """测试回滚配置"""
        # 先创建变更
        client.put("/api/config", json={
            "items": [{"key": "llm.model", "value": "gpt-4o-rollback-test"}],
            "test_connection": False,
        })
        # 获取历史
        history = client.get("/api/config/history").json()
        if history.get("revisions"):
            rev_num = history["revisions"][0]["revision_number"]
            resp = client.post("/api/config/rollback", json={"revision_number": rev_num})
            assert resp.status_code == 200

    def test_rollback_nonexistent_revision(self, client):
        """测试回滚不存在的修订号"""
        resp = client.post("/api/config/rollback", json={"revision_number": 99999})
        assert resp.status_code == 404

    def test_export_configs(self, client):
        """测试导出配置"""
        resp = client.get("/api/config/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "exported_at" in data
        assert data["version"] == "1.0"

    def test_import_configs(self, client):
        """测试导入配置"""
        resp = client.post("/api/config/import", json={
            "items": [{"key": "llm.model", "value": "gpt-4o-imported"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("imported_count", 0) >= 1 or data.get("saved_count", 0) >= 1

    def test_import_configs_skips_redacted(self, client):
        """测试导入跳过 REDACTED 字段"""
        resp = client.post("/api/config/import", json={
            "items": [
                {"key": "llm.model", "value": "gpt-4o-imported"},
                {"key": "llm.api_key", "value": "***REDACTED***"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("skipped_count", 0) == 1

    def test_test_connection(self, client):
        """测试连接测试端点"""
        resp = client.post("/api/config/test", json={
            "categories": ["auth"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_test_connection_unknown_category(self, client):
        """测试连接测试未知类别"""
        resp = client.post("/api/config/test", json={
            "categories": ["unknown"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert any(r["category"] == "unknown" for r in data["results"])
