"""TDD：extractor-mode 专用端点（子项目 C E-14/E-15/E-16）。

GET 返回 available_modes/default_mode/descriptions/effective_mode；
PUT（admin）写 sa_config；非法 mode → 400。用 fake SaConfigService 隔离存储。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.sa_config.api import extractor_mode_routes as R


class _FakeSvc:
    def __init__(self):
        self.store = {}

    def list_configs(self, scope=None):
        items = [v for v in self.store.values() if scope is None or v["scope"] == scope]
        return {"status": "ok", "items": items, "count": len(items)}

    def set_config(self, scope, config_key, value, updated_by="system"):
        self.store[(scope, config_key)] = {
            "id": f"{scope}::{config_key}", "scope": scope,
            "config_key": config_key,
            "config_value": value if isinstance(value, dict) else {"value": value},
            "updated_by": updated_by, "created_at": "2026-10-09T00:00:00+00:00",
            "updated_at": "2026-10-09T00:00:00+00:00",
        }
        e = self.store[(scope, config_key)]
        return {"status": "ok", **e}


@pytest.fixture
def client(monkeypatch):
    import odap.biz.data.qa.pipeline.understanding.extractor_mode as em
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: None)
    monkeypatch.delenv("EXTRACTOR_MODE", raising=False)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[R.verify_admin] = lambda: {"id": "admin1", "role": "admin"}
    app.dependency_overrides[R.get_current_user] = lambda: {"id": "u1", "role": "viewer"}
    monkeypatch.setattr(R, "_svc_override", _FakeSvc())
    return TestClient(app)


def test_get_defaults(client):
    r = client.get("/api/semantic-admin/extractor-mode")
    assert r.status_code == 200
    b = r.json()
    assert b["default_mode"] == "query"
    assert b["available_modes"] == ["off", "inject", "query"]
    assert b["effective_mode"] == "query"
    assert b["mode"] is None                       # 未显式配置
    assert set(b["descriptions"].keys()) == {"off", "inject", "query"}


def test_put_valid_mode_persists_and_reflects(client):
    r = client.put("/api/semantic-admin/extractor-mode", json={"mode": "inject"})
    assert r.status_code == 200
    assert r.json()["effective_mode"] == "inject"
    assert r.json()["mode"] == "inject"
    # 再 GET 仍为 inject（持久化 + effective 反映）
    r2 = client.get("/api/semantic-admin/extractor-mode")
    assert r2.json()["effective_mode"] == "inject"


def test_put_invalid_mode_400(client):
    r = client.put("/api/semantic-admin/extractor-mode", json={"mode": "bogus"})
    assert r.status_code == 400


def test_put_requires_admin(client):
    # 移除 admin override → verify_admin 生效（未认证 → 401/403）
    app = client.app
    app.dependency_overrides.pop(R.verify_admin, None)
    r = client.put("/api/semantic-admin/extractor-mode", json={"mode": "off"})
    assert r.status_code in (401, 403)
