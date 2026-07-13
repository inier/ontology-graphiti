"""Semantic Admin - USL Routes 层 HTTP 状态码测试。

覆盖（使用 FastAPI TestClient + tmp_path 真实 SQLite DB，不依赖全局 app）：
 1. GET    /domains             → 200，标准分页格式
 2. POST   /domains             → 200，创建成功；400 参数/业务错误；422 Pydantic 校验
 3. GET    /domains/{id}        → 200 成功 / 404 不存在
 4. PUT    /domains/{id}        → 200 更新 / 404 不存在 / 400 业务错误
 5. DELETE /domains/{id}        → 200 删除 / 404 不存在
 6. Term CRUD：同义词关键字搜索 + semantic_type 过滤 HTTP 200
 7. POST disjoint (term_a==term_b) → 400 业务错误（由 services 错误转 HTTPException 400，不是 500）
 8. POST term 引用不存在 domain_id → 400（Impl ValueError → services error → routes 400）
 9. PUT term(id not exist)      → 404
10. Hierarchy / PropertySpec / Cardinality GET 不存在 → 404
11. verify_admin 保护：当 role != admin 时 POST/PUT/DELETE 返回 403
    （只读 GET 用 get_current_user，登录即允许）
12. **关键**：except HTTPException: raise 透传验证。故意触发一个 404/400，
    确认响应 status_code 不是 500（说明透传未被外层 except Exception 兜底吞掉）
13. POST 缺少必填字段 → 422（Pydantic 校验失败由 FastAPI 自动处理）
14. Pydantic strict=True 校验：传字段类型错误 → 422
15. list terms 非法 semantic_type 值 → 400（由 services error 翻译）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.usl_manager.api.routes import (
    router as usl_router,
    usl_service as _global_usl_service,
)
from odap.biz.semantic_admin.usl_manager.impl import UslManagerServiceImpl
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
from odap.infra.security.jwt_auth import get_current_user, verify_admin


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def admin_client(tmp_path: Path):
    """独立 TestClient，mock admin + 独立 tmp_path SQLite DB。"""
    app = FastAPI()
    app.include_router(usl_router)

    async def _admin_user():
        return {"user_id": "admin-1", "role": "admin",
                "ws_id": "ws1", "ws_role": "owner"}

    # override get_current_user（读保护）+ verify_admin（写保护）
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[verify_admin] = _admin_user

    # 替换模块级 usl_service 的 storage / repository，使用 tmp_path 真实 DB
    db_path = str(tmp_path / "routes.db")
    storage = SQLiteUslStorage(db_path)
    repository = UslManagerServiceImpl(storage=storage)
    _global_usl_service.storage = storage
    _global_usl_service.repository = repository

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def reader_client(tmp_path: Path):
    """只读角色：get_current_user 通过，但 verify_admin 将返回 403。"""
    app = FastAPI()
    app.include_router(usl_router)

    async def _reader_user():
        return {"user_id": "reader-1", "role": "member",
                "ws_id": "ws1", "ws_role": "reader"}

    # get_current_user → reader；verify_admin 不覆盖，会实际调用校验 role != admin 时抛 403
    # 但真实 verify_admin 需要 JWT token decode，这里直接简化：override verify_admin 主动 raise 403
    from fastapi import HTTPException

    async def _block_non_admin():
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[get_current_user] = _reader_user
    app.dependency_overrides[verify_admin] = _block_non_admin

    db_path = str(tmp_path / "routes_reader.db")
    storage = SQLiteUslStorage(db_path)
    repository = UslManagerServiceImpl(storage=storage)
    _global_usl_service.storage = storage
    _global_usl_service.repository = repository

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# 辅助: 快速创建一个 domain
def _post_domain(client: TestClient, code: str = "d1") -> str:
    r = client.post("/api/semantic-admin/usl/domains", json={
        "code": code, "display_name": f"{code} 领域",
        "en_mapping": {"势力": "Faction", "人物": "Character"},
    })
    assert r.status_code == 200, f"创建领域失败: {r.status_code} {r.text}"
    return r.json()["id"]


# =====================================================================
# 1. Domain HTTP 状态码
# =====================================================================


class TestDomainRoutesHttp:
    def test_list_domains_empty_200_paged_format(self, admin_client):
        r = admin_client.get("/api/semantic-admin/usl/domains")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"items", "total", "page", "page_size"}
        assert body["total"] == 0
        assert body["items"] == []

    def test_post_create_200_and_get_by_id_200(self, admin_client):
        did = _post_domain(admin_client, "x")
        # GET by id
        r = admin_client.get(f"/api/semantic-admin/usl/domains/{did}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == did
        assert body["code"] == "x"

    def test_get_domain_not_found_404_not_500(self, admin_client):
        """关键断言：404 不会被 except Exception 包成 500。"""
        r = admin_client.get("/api/semantic-admin/usl/domains/DOES_NOT_EXIST")
        assert r.status_code == 404, (
            f"应为 404（except HTTPException: raise 透传失败），实际: {r.status_code} {r.text}"
        )
        assert "不存在" in r.json()["detail"]

    def test_put_update_domain_200(self, admin_client):
        did = _post_domain(admin_client, "u")
        r = admin_client.put(f"/api/semantic-admin/usl/domains/{did}", json={
            "display_name": "新名字",
            "description": "new description",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["display_name"] == "新名字"
        assert body["description"] == "new description"

    def test_put_domain_not_found_404_transparent(self, admin_client):
        """PUT 不存在 id → 404，不是 500。"""
        r = admin_client.put("/api/semantic-admin/usl/domains/NOPE", json={
            "display_name": "X",
        })
        assert r.status_code == 404

    def test_delete_domain_200_and_again_404(self, admin_client):
        did = _post_domain(admin_client, "del")
        r = admin_client.delete(f"/api/semantic-admin/usl/domains/{did}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # 再删一次 → 404
        r = admin_client.delete(f"/api/semantic-admin/usl/domains/{did}")
        assert r.status_code == 404

    def test_post_missing_code_pydantic_422_not_500(self, admin_client):
        """缺少必填 code → FastAPI Pydantic 校验 422；不是 500。"""
        r = admin_client.post("/api/semantic-admin/usl/domains", json={
            "display_name": "no code",
        })
        assert r.status_code == 422

    def test_post_same_code_uniq_conflict_does_not_raise(self, admin_client):
        """Storage 层 ON CONFLICT DO UPDATE，因此不会 IntegrityError，返回 200。"""
        _post_domain(admin_client, "shared")
        r = admin_client.post("/api/semantic-admin/usl/domains", json={
            "code": "shared", "display_name": "第二个",
        })
        assert r.status_code == 200
        # 总数为 1
        rl = admin_client.get("/api/semantic-admin/usl/domains")
        assert rl.json()["total"] == 1


# =====================================================================
# 2. Term HTTP 状态码
# =====================================================================


class TestTermRoutesHttp:
    def test_post_term_bad_domain_id_400_not_500(self, admin_client):
        """Impl 层 raise ValueError('领域不存在') → services 转 error dict
        → routes 转 HTTPException 400，不是 500。"""
        r = admin_client.post("/api/semantic-admin/usl/terms", json={
            "domain_id": "BAD-DOMAIN-ID",
            "canonical": "人物",
        })
        assert r.status_code == 400, (
            f"应为 400（impl ValueError → services error → routes HTTPException 400），"
            f"实际: {r.status_code} {r.text}"
        )
        assert "领域不存在" in r.json()["detail"]

    def test_post_term_success_and_get_404_transparent(self, admin_client):
        did = _post_domain(admin_client, "td")
        r = admin_client.post("/api/semantic-admin/usl/terms", json={
            "domain_id": did, "canonical": "势力",
            "semantic_type": "对象类型",
            "synonyms": ["阵营", "国家"],
        })
        assert r.status_code == 200
        tid = r.json()["id"]
        # 404 透传测试
        r = admin_client.get("/api/semantic-admin/usl/terms/NOPE")
        assert r.status_code == 404
        # GET 正常
        r = admin_client.get(f"/api/semantic-admin/usl/terms/{tid}")
        assert r.status_code == 200 and r.json()["canonical"] == "势力"

    def test_list_terms_filter_semantic_type_and_synonym_keyword(self, admin_client):
        did = _post_domain(admin_client, "tf")
        admin_client.post("/api/semantic-admin/usl/terms", json={
            "domain_id": did, "canonical": "A", "semantic_type": "关系类型",
            "synonyms": ["队伍"],
        })
        admin_client.post("/api/semantic-admin/usl/terms", json={
            "domain_id": did, "canonical": "B", "semantic_type": "对象类型",
        })
        # semantic_type 过滤
        r = admin_client.get(
            "/api/semantic-admin/usl/terms",
            params={"semantic_type": "关系类型"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["canonical"] == "A"
        # 同义词关键字
        r = admin_client.get(
            "/api/semantic-admin/usl/terms",
            params={"synonym_keyword": "队伍"},
        )
        assert r.status_code == 200 and r.json()["total"] == 1

    def test_list_terms_invalid_semantic_type_400(self, admin_client):
        """非法 semantic_type → Impl 校验 ValueError → services error → 400。"""
        r = admin_client.get(
            "/api/semantic-admin/usl/terms",
            params={"semantic_type": "NOT_A_TYPE"},
        )
        assert r.status_code == 400
        assert "非法 semantic_type" in r.json()["detail"]

    def test_put_term_not_found_404(self, admin_client):
        r = admin_client.put("/api/semantic-admin/usl/terms/NO", json={
            "definition": "x",
        })
        assert r.status_code == 404


# =====================================================================
# 3. Disjoint - term_a == term_b 业务错误 400
# =====================================================================


class TestDisjointRoutesHttp:
    def test_post_term_a_equals_b_400_not_500(self, admin_client):
        """Services 层直接判断 term_a == term_b 返回 error dict → routes 400。"""
        did = _post_domain(admin_client, "dd")
        r = admin_client.post("/api/semantic-admin/usl/disjoint-pairs", json={
            "domain_id": did, "term_a": "X", "term_b": "X", "reason": "",
        })
        assert r.status_code == 400, (
            f"应为 400（services 直接拒绝 term_a==term_b），实际: {r.status_code} {r.text}"
        )
        assert "不能相同" in r.json()["detail"]

    def test_get_pair_404(self, admin_client):
        r = admin_client.get("/api/semantic-admin/usl/disjoint-pairs/NOT")
        assert r.status_code == 404


# =====================================================================
# 4. Hierarchy / PropertySpec / Cardinality - 404 GET not found
# =====================================================================


class TestOtherRoutes404:
    def test_hierarchy_get_404(self, admin_client):
        r = admin_client.get("/api/semantic-admin/usl/hierarchy/N")
        assert r.status_code == 404

    def test_property_spec_get_404(self, admin_client):
        r = admin_client.get("/api/semantic-admin/usl/property-specs/N")
        assert r.status_code == 404

    def test_cardinality_get_404(self, admin_client):
        r = admin_client.get("/api/semantic-admin/usl/cardinalities/N")
        assert r.status_code == 404


# =====================================================================
# 5. verify_admin 写保护（POST/PUT/DELETE 非 admin 返回 403）
# =====================================================================


class TestAdminWriteProtection:
    def test_get_reader_allowed_200(self, reader_client):
        """读操作 GET 只要求登录（reader 可）。"""
        r = reader_client.get("/api/semantic-admin/usl/domains")
        assert r.status_code == 200

    def test_post_domain_blocked_403_for_reader(self, reader_client):
        """写操作 POST 要求 admin，reader 被 verify_admin 拒绝。"""
        r = reader_client.post("/api/semantic-admin/usl/domains", json={
            "code": "x", "display_name": "X",
        })
        assert r.status_code == 403
        # 且不是 500
        assert "写操作需要" in r.json()["detail"]

    def test_put_and_delete_blocked_403_for_reader(self, reader_client):
        """PUT/DELETE 也被保护。"""
        r = reader_client.put("/api/semantic-admin/usl/domains/ANY", json={})
        assert r.status_code == 403
        r = reader_client.delete("/api/semantic-admin/usl/domains/ANY")
        assert r.status_code == 403


# =====================================================================
# 6. Pydantic strict=True 校验：字段类型错误 → 422
# =====================================================================


class TestStrictSchemaValidation:
    def test_post_domain_synonyms_wrong_type_422(self, admin_client):
        """canonical_terms synonyms 字段在 schema 中不存在 domain 创建里；
        但在 term 创建里 stoplist_flag 必须是 bool；传字符串 → 422。"""
        did = _post_domain(admin_client, "sv")
        r = admin_client.post("/api/semantic-admin/usl/terms", json={
            "domain_id": did,
            "canonical": "T",
            "stoplist_flag": "yes please",  # 错误：不是 bool
        })
        assert r.status_code == 422

    def test_extra_fields_forbidden_422(self, admin_client):
        """extra='forbid' → 传未知字段 → 422。"""
        r = admin_client.post("/api/semantic-admin/usl/domains", json={
            "code": "ef", "display_name": "E",
            "unknown_field_xyz": 123,  # 非法 extra 字段
        })
        assert r.status_code == 422
