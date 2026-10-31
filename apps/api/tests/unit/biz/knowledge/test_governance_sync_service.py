"""仓库 ↔ Wiki 双向同步测试（AC-15 / AC-16 / AC-17）。

覆盖：导入幂等与哈希重算、路径白名单与穿越防护、导出双重门禁（写权限 + 审批）。
"""

from __future__ import annotations

import pytest

from odap.common.api_errors import ApiError
from odap.common.ids import content_hash

DOC_PATH = "docs/02-architecture/return-rate.md"
BODY = "退货率 = 退货订单数 / 成交订单数（按签收日期归集）。\n"

DOC_TEXT = """---
title: 订单退货率口径
status: published
owner: u-data-owner
version: 1.2.0
content_hash: sha256:declared-but-stale
last_verified: 2026-10-01
tags: [metric, order]
citations:
  - kind: metric
    ref: metric:order_return_rate@2026Q3
---

""" + BODY

EDITOR = {"sub": "u-editor", "roles": ["editor"]}
VIEWER = {"sub": "u-viewer", "roles": ["viewer"]}


@pytest.fixture
def doc_file(repo_root):
    path = repo_root / DOC_PATH
    path.write_text(DOC_TEXT, encoding="utf-8")
    return path


class TestImport:
    def test_import_creates_entry_and_governed_doc(self, sync_service, doc_file):
        result = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        assert result["action"] == "created"
        assert result["source_ref"] == f"repo:{DOC_PATH}"
        assert result["status"] == "published"
        assert result["title"] == "订单退货率口径"
        # content_hash 按真实正文重算，不信任 front-matter 里的声明
        assert result["content_hash"] == content_hash(BODY)
        assert result["content_hash"] != "sha256:declared-but-stale"

        governed = sync_service.docs.get_by_source_ref(f"repo:{DOC_PATH}")
        assert governed is not None
        assert governed.content_hash == result["content_hash"]
        assert governed.role == ""

    def test_import_is_idempotent_by_source_ref(self, sync_service, doc_file):
        first = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        second = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        assert second["action"] == "updated"
        assert second["id"] == first["id"]
        assert second["version"] == first["version"]  # 内容未变 → 不递增版本

    def test_import_detects_content_change_and_bumps_version(self, sync_service, doc_file):
        first = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        doc_file.write_text(DOC_TEXT.replace("按签收日期归集", "按客户确认收货日期归集"),
                            encoding="utf-8")
        second = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        assert second["version"] != first["version"]

    def test_import_writes_citations(self, sync_service, doc_file):
        result = sync_service.import_from_repo(DOC_PATH, actor_id="u-importer")
        citations = sync_service.citations.list_outgoing(result["id"])
        assert [(c.kind.value, c.ref) for c in citations] == [
            ("metric", "metric:order_return_rate@2026Q3")
        ]

    def test_missing_owner_without_actor_is_rejected(self, sync_service, repo_root):
        path = repo_root / "docs" / "no-owner.md"
        path.write_text("---\ntitle: 无责任人文档\n---\n\n正文。\n", encoding="utf-8")
        with pytest.raises(ApiError) as excinfo:
            sync_service.import_from_repo("docs/no-owner.md")
        assert excinfo.value.error_code == "WIKI_OWNER_REQUIRED"


class TestPathWhitelist:
    @pytest.mark.parametrize(
        "path",
        [
            "docs/../etc/passwd.md",
            "apps/api/odap/tasks.py",
            "docs/02-architecture/return-rate.txt",
            "secrets.md",
        ],
    )
    def test_non_whitelisted_paths_rejected(self, sync_service, path):
        with pytest.raises(ApiError) as excinfo:
            sync_service.import_from_repo(path)
        assert excinfo.value.error_code == "WIKI_IMPORT_PATH_INVALID"
        assert excinfo.value.status_code == 400

    def test_missing_file_raises_404(self, sync_service):
        with pytest.raises(ApiError) as excinfo:
            sync_service.import_from_repo("docs/does-not-exist.md")
        assert excinfo.value.error_code == "WIKI_IMPORT_SOURCE_NOT_FOUND"
        assert excinfo.value.status_code == 404

    def test_invalid_status_in_front_matter_rejected(self, sync_service, repo_root):
        path = repo_root / "docs" / "bad-status.md"
        path.write_text("---\ntitle: 退货率口径\nowner: u-owner\nstatus: 已发布\n---\n\n正文。\n",
                        encoding="utf-8")
        with pytest.raises(ApiError) as excinfo:
            sync_service.import_from_repo("docs/bad-status.md")
        assert excinfo.value.error_code == "DOC_STATUS_INVALID"


class TestExport:
    def _published_entry(self, entry_service):
        entry = entry_service.create(
            title="订单退货率口径", content=BODY, owner="u-owner",
            tags=["metric"], citations=[{"kind": "metric",
                                         "ref": "metric:order_return_rate@2026Q3"}],
        )
        return entry_service.publish(entry.id, actor_id="u-owner")

    def test_export_requires_write_permission(self, sync_service, entry_service):
        entry = self._published_entry(entry_service)
        with pytest.raises(ApiError) as excinfo:
            sync_service.export_to_repo(
                entry_id=entry.id, target_path=DOC_PATH, approval_id="apr-1", user=VIEWER
            )
        assert excinfo.value.error_code == "WIKI_EXPORT_FORBIDDEN"
        assert excinfo.value.status_code == 403
        assert excinfo.value.detail["reason"] == "write_permission_denied"

    def test_export_requires_approval_id(self, sync_service, entry_service, repo_root):
        entry = self._published_entry(entry_service)
        with pytest.raises(ApiError) as excinfo:
            sync_service.export_to_repo(
                entry_id=entry.id, target_path=DOC_PATH, approval_id=None, user=EDITOR
            )
        assert excinfo.value.detail["reason"] == "approval_missing"
        assert not (repo_root / DOC_PATH).exists()  # 文件零改动

    def test_export_rejects_unapproved(self, entry_service, kb_db, repo_root):
        from odap.biz.knowledge.governance.services.sync_service import SyncService

        service = SyncService(db_path=kb_db, approval_checker=lambda _id: False)
        entry = self._published_entry(entry_service)
        with pytest.raises(ApiError) as excinfo:
            service.export_to_repo(
                entry_id=entry.id, target_path=DOC_PATH, approval_id="apr-rejected", user=EDITOR
            )
        assert excinfo.value.detail["reason"] == "approval_not_granted"
        assert not (repo_root / DOC_PATH).exists()

    def test_export_writes_front_matter_and_updates_last_verified(self, sync_service,
                                                                 entry_service, repo_root):
        entry = self._published_entry(entry_service)
        result = sync_service.export_to_repo(
            entry_id=entry.id, target_path=DOC_PATH, approval_id="apr-ok", user=EDITOR
        )
        written = (repo_root / DOC_PATH).read_text(encoding="utf-8")
        assert result["target_path"] == DOC_PATH
        assert f"id: {entry.id}" in written
        assert "title: 订单退货率口径" in written
        assert "metric:order_return_rate@2026Q3" in written

        from odap.biz.knowledge.governance.services.frontmatter import parse_document

        front_matter, body = parse_document(written)
        assert front_matter["owner"] == "u-owner"
        assert body.strip() == BODY.strip()

        reloaded = entry_service.get(entry.id)
        assert reloaded.last_verified is not None
        assert reloaded.source_ref == f"repo:{DOC_PATH}"

    def test_export_unknown_entry_raises_404(self, sync_service):
        with pytest.raises(ApiError) as excinfo:
            sync_service.export_to_repo(
                entry_id="doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A", target_path=DOC_PATH,
                approval_id="apr-ok", user=EDITOR,
            )
        assert excinfo.value.error_code == "WIKI_ENTRY_NOT_FOUND"
