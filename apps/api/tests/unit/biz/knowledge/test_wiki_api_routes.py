"""Wiki / 文档治理路由层测试（AC-02 / AC-04 / AC-08 / AC-09 / AC-56）。

重点验证：HTTP 状态码 + 统一错误契约 `{error_code, message, detail, trace_id}`
（AC-56 禁止模糊文案；trace_id 支持 `X-Request-ID` 透传）。
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

TRACE_PATTERN = re.compile(r"^urn:odap:trace:[0-9A-HJKMNP-TV-Z]{26}$")
CONTENT = "退货率 = 退货订单数 / 成交订单数（按签收日期归集）。"


@pytest.fixture
def client(kb_db, repo_root):
    from odap.biz.knowledge.governance.api import routes as governance_routes
    from odap.biz.knowledge.governance.services.doc_service import DocService
    from odap.biz.knowledge.governance.services.supersede_service import SupersedeService
    from odap.biz.knowledge.governance.services.sync_service import SyncService
    from odap.biz.knowledge.governance.services.verify_service import VerifyService
    from odap.biz.knowledge.wiki.api import routes as wiki_routes
    from odap.biz.knowledge.wiki.services.citation_service import CitationService
    from odap.biz.knowledge.wiki.services.dedupe_service import DedupeService
    from odap.biz.knowledge.wiki.services.entry_service import WikiEntryService
    from odap.biz.knowledge.wiki.services.version_service import VersionService
    from odap.infra.middleware.api_error_handler import register_api_error_handler
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(wiki_routes.router)
    app.include_router(governance_routes.router)
    register_api_error_handler(app)

    async def _user():
        return {"sub": "u-owner", "roles": ["editor"], "workspace_id": "ws-supply"}

    app.dependency_overrides[get_current_user] = _user

    wiki_routes.set_services(
        entry=WikiEntryService(db_path=kb_db),
        version=VersionService(db_path=kb_db),
        citation=CitationService(db_path=kb_db),
        sync=SyncService(db_path=kb_db, approval_checker=lambda _id: True),
    )
    governance_routes.set_services(
        doc=DocService(db_path=kb_db, today="2026-10-17"),
        supersede=SupersedeService(db_path=kb_db),
        verify=VerifyService(db_path=kb_db, today="2026-10-17"),
        dedupe=DedupeService(db_path=kb_db),
    )
    with TestClient(app) as test_client:
        yield test_client
    wiki_routes.reset_services()
    governance_routes.reset_services()


def _create(client, **overrides):
    payload = {"title": "订单退货率口径", "content": CONTENT, "owner": "u-owner"}
    payload.update(overrides)
    return client.post("/api/v1/wiki/entries", json=payload)


class TestWikiEntryEndpoints:
    def test_create_returns_201_and_envelope(self, client):
        response = _create(client)
        assert response.status_code == 201
        body = response.json()
        assert body["code"] == 0
        assert body["data"]["version"] == "0.1.0"
        assert body["data"]["status"] == "draft"

    def test_missing_owner_returns_400_with_error_contract(self, client):
        response = _create(client, owner=None)
        assert response.status_code == 400
        body = response.json()
        assert set(body) == {"error_code", "message", "detail", "trace_id"}
        assert body["error_code"] == "WIKI_OWNER_REQUIRED"
        assert "owner" in body["message"]
        assert TRACE_PATTERN.match(body["trace_id"])
        assert response.headers["X-Request-ID"] == body["trace_id"]

    def test_request_id_header_is_propagated(self, client):
        response = client.get(
            "/api/v1/wiki/entries/doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A",
            headers={"X-Request-ID": "urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A"},
        )
        assert response.status_code == 404
        assert response.json()["trace_id"] == "urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A"

    def test_get_missing_entry_returns_404(self, client):
        response = client.get("/api/v1/wiki/entries/doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A")
        assert response.status_code == 404
        assert response.json()["error_code"] == "WIKI_ENTRY_NOT_FOUND"

    def test_patch_with_stale_version_returns_409(self, client):
        created = _create(client).json()["data"]
        client.patch(f"/api/v1/wiki/entries/{created['id']}",
                     json={"content": CONTENT + "补充：按客户确认收货日期。", "version": "0.1.0"})
        response = client.patch(f"/api/v1/wiki/entries/{created['id']}",
                               json={"tags": ["metric"], "version": "0.1.0"})
        assert response.status_code == 409
        assert response.json()["error_code"] == "WIKI_VERSION_CONFLICT"

    def test_publish_duplicate_returns_409_with_conflict_id(self, client):
        first = _create(client).json()["data"]
        second = _create(client).json()["data"]
        assert client.post(f"/api/v1/wiki/entries/{first['id']}/publish").status_code == 200
        response = client.post(f"/api/v1/wiki/entries/{second['id']}/publish")
        assert response.status_code == 409
        body = response.json()
        assert body["error_code"] == "WIKI_DUPLICATE_CONTENT"
        assert body["detail"]["conflicting_entry_id"] == first["id"]

    def test_versions_and_references_endpoints(self, client):
        created = _create(client).json()["data"]
        versions = client.get(f"/api/v1/wiki/entries/{created['id']}/versions")
        assert versions.status_code == 200
        assert [v["change_note"] for v in versions.json()["data"]] == ["create"]

        references = client.get(f"/api/v1/wiki/entries/{created['id']}/references")
        assert references.status_code == 200
        graph = references.json()["data"]
        assert graph["nodes"][0]["id"] == created["id"]
        assert graph["outgoing"] == [] and graph["incoming"] == []

    def test_archive_returns_archived_status(self, client):
        created = _create(client).json()["data"]
        response = client.delete(f"/api/v1/wiki/entries/{created['id']}")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "archived"

    def test_list_entries_rejects_unknown_status(self, client):
        response = client.get("/api/v1/wiki/entries", params={"status": "在写"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "WIKI_INVALID_STATUS_TRANSITION"

    def test_import_from_repo_endpoint(self, client, repo_root):
        path = repo_root / "docs" / "02-architecture" / "return-rate.md"
        path.write_text("---\ntitle: 订单退货率口径\nowner: u-owner\n---\n\n" + CONTENT,
                        encoding="utf-8")
        response = client.post("/api/v1/wiki/sync/import",
                               json={"source_ref": "docs/02-architecture/return-rate.md"})
        assert response.status_code == 201
        assert response.json()["data"]["action"] == "created"

    def test_export_without_approval_returns_403(self, client):
        created = _create(client).json()["data"]
        response = client.post("/api/v1/wiki/sync/export",
                               json={"entry_id": created["id"],
                                     "target_path": "docs/02-architecture/return-rate.md"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "WIKI_EXPORT_FORBIDDEN"


class TestGovernanceEndpoints:
    def test_documents_list_has_five_fields(self, client, repo_root):
        # 纳管文档来自仓库导入（governed_documents）；wiki 条目有自己的列表端点
        path = repo_root / "docs" / "02-architecture" / "return-rate.md"
        path.write_text("---\ntitle: 订单退货率口径\nowner: u-owner\nrole: be\n---\n\n" + CONTENT,
                        encoding="utf-8")
        client.post("/api/v1/wiki/sync/import",
                    json={"source_ref": "docs/02-architecture/return-rate.md"})

        response = client.get("/api/v1/docs/governance/documents")
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["total"] >= 1
        for field in ("owner", "status", "role", "last_verified", "superseded_by"):
            assert field in body["items"][0]
        assert "content" not in body["items"][0]

    def test_document_detail_missing_returns_404(self, client):
        response = client.get("/api/v1/docs/governance/documents/gov-missing")
        assert response.status_code == 404
        assert response.json()["error_code"] == "DOC_NOT_FOUND"

    def test_verify_returns_pass_alias(self, client):
        _create(client)
        response = client.post("/api/v1/docs/governance/verify")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "pass" in data
        assert isinstance(data["counts"], dict)

    def test_dedupe_returns_list(self, client):
        _create(client)
        _create(client, title="订单退货率口径（副本）")
        response = client.get("/api/v1/docs/governance/dedupe")
        assert response.status_code == 200
        candidates = response.json()["data"]
        assert len(candidates) == 1
        assert candidates[0]["similarity"] == 1.0
        assert candidates[0]["canonical_id"] == min(candidates[0]["doc_ids"])

    def test_supersede_missing_document_returns_404(self, client):
        response = client.post("/api/v1/docs/governance/documents/gov-missing/supersede",
                               json={"superseded_by": "gov-other"})
        assert response.status_code == 404
        assert response.json()["error_code"] == "DOC_NOT_FOUND"

    def test_supersede_self_returns_400(self, client):
        created = _create(client).json()["data"]
        response = client.post(
            f"/api/v1/docs/governance/documents/{created['id']}/supersede",
            json={"superseded_by": created["id"]},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "DOC_SUPERSEDE_SELF"
