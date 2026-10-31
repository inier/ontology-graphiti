"""文档治理机械校验 + 纳管文档查询测试（AC-09 / AC-11 / AC-12 / AC-13 / AC-14）。"""

from __future__ import annotations

import pytest

from odap.common.api_errors import ApiError
from odap.common.ids import content_hash
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.biz.knowledge.models.common import DocStatus

RETURN_RATE = "退货率 = 退货订单数 / 成交订单数（按签收日期归集）。"
FULFILLMENT = "履约率 = 按期交付批次 / 总交付批次（按供应商维度聚合）。"
FRESH = "2026-10-01"
STALE = "2020-01-01"
SOURCE_REF = "repo:docs/02-architecture/return-rate.md"


def _doc(doc_id: str, title: str, *, owner="u-owner", verified=FRESH, content=RETURN_RATE,
         source_ref=None, status=DocStatus.PUBLISHED):
    return GovernedDoc(
        id=doc_id, title=title, status=status, owner=owner, version="1.0.0",
        source_ref=source_ref, content_hash=content_hash(content), content=content,
        last_verified=verified, role="be",
        created_at="2026-09-01T00:00:00+00:00", updated_at="2026-09-01T00:00:00+00:00",
    )


def _link_entry_to_source_ref(entry_service, entry_id: str, source_ref: str) -> None:
    """把手工创建的条目挂到仓库路径上（create 不接收 source_ref，模拟导入后的状态）。"""
    entry_service.entries.update(entry_id, {"source_ref": source_ref})


class TestVerifyReport:
    def test_clean_set_passes(self, doc_repo, verify_service):
        doc_repo.upsert(_doc("gov-clean", "退货率口径说明"))
        report = verify_service.run()
        assert report.pass_ is True
        assert report.errors == 0
        assert report.checked == 1

    def test_missing_owner_is_error(self, doc_repo, verify_service):
        doc_repo.upsert(_doc("gov-no-owner", "履约率口径", owner=None, content=FULFILLMENT))
        report = verify_service.run()
        assert report.pass_ is False
        assert report.counts["MISSING_OWNER"] == 1
        issue = [i for i in report.issues if i.code == "MISSING_OWNER"][0]
        assert issue.severity == "error"
        assert issue.code_api == "missing_owner"  # 兼容 openapi 枚举

    def test_dangling_reference_is_error(self, entry_service, verify_service):
        entry_service.create(
            title="季度经营复盘",
            content="退货率恶化，引用《退货率口径（已删除）》。",
            owner="u-owner",
            citations=[{"kind": "doc", "ref": "doc-gov-does-not-exist"}],
        )
        report = verify_service.run()
        assert report.pass_ is False
        assert report.counts["DANGLING_REF"] == 1
        detail = [i for i in report.issues if i.code == "DANGLING_REF"][0].detail
        assert "doc-gov-does-not-exist" in detail

    def test_reference_to_existing_entry_is_not_dangling(self, entry_service, verify_service):
        target = entry_service.create(title="退货率口径", content=RETURN_RATE, owner="u-owner")
        entry_service.create(
            title="季度复盘", content="引用退货率口径。", owner="u-owner",
            citations=[{"kind": "doc", "ref": f"entry:{target.id}"}],
        )
        report = verify_service.run()
        assert "DANGLING_REF" not in report.counts

    def test_non_doc_citation_not_judged_here(self, entry_service, verify_service):
        entry_service.create(
            title="退货率指标引用", content=RETURN_RATE, owner="u-owner",
            citations=[{"kind": "metric", "ref": "metric:order_return_rate@2026Q3"}],
        )
        report = verify_service.run()
        assert "DANGLING_REF" not in report.counts

    def test_stale_verified_is_warning_not_error(self, doc_repo, verify_service):
        doc_repo.upsert(_doc("gov-stale", "历史退货率口径", verified=STALE))
        report = verify_service.run()
        assert report.counts["STALE"] == 1
        stale_issue = [i for i in report.issues if i.code == "STALE"][0]
        assert stale_issue.severity == "warning"
        assert report.warnings >= 1
        assert report.pass_ is True  # warning 不阻断

    def test_duplicate_hash_detected_across_sources(self, doc_repo, entry_service,
                                                   verify_service):
        doc_repo.upsert(_doc("gov-dup-a", "退货率口径 A"))
        entry_service.create(title="退货率口径 B", content=RETURN_RATE, owner="u-owner")
        report = verify_service.run()
        assert report.counts["DUPLICATE_HASH"] == 2

    def test_same_source_ref_projection_not_counted_as_duplicate(self, doc_repo, entry_service,
                                                                verify_service):
        doc_repo.upsert(_doc("gov-proj", "退货率口径", source_ref=SOURCE_REF))
        entry = entry_service.create(title="退货率口径", content=RETURN_RATE, owner="u-owner")
        _link_entry_to_source_ref(entry_service, entry.id, SOURCE_REF)
        report = verify_service.run()
        assert "DUPLICATE_HASH" not in report.counts

    def test_report_serializes_pass_alias(self, doc_repo, verify_service):
        doc_repo.upsert(_doc("gov-alias", "退货率口径"))
        payload = verify_service.run().model_dump(mode="json", by_alias=True)
        assert payload["pass"] is True
        assert "issues" in payload and "counts" in payload


class TestDocService:
    def test_list_returns_required_five_fields_without_content(self, doc_repo, doc_service):
        doc_repo.upsert(_doc("gov-list", "退货率口径说明"))
        page = doc_service.list_documents()
        assert page["total"] == 1
        item = page["items"][0]
        for field in ("owner", "status", "role", "last_verified", "superseded_by"):
            assert field in item
        assert "content" not in item
        assert item["stale"] is False

    def test_stale_filter(self, doc_repo, doc_service):
        doc_repo.upsert(_doc("gov-stale", "旧退货率口径", verified=STALE))
        doc_repo.upsert(_doc("gov-fresh", "新退货率口径", content=FULFILLMENT))
        stale_page = doc_service.list_documents(stale=True)
        assert [i["id"] for i in stale_page["items"]] == ["gov-stale"]
        assert stale_page["items"][0]["stale"] is True

    def test_no_owner_filter(self, doc_repo, doc_service):
        doc_repo.upsert(_doc("gov-none", "缺责任人文档", owner=None))
        doc_repo.upsert(_doc("gov-ok", "正常文档", content=FULFILLMENT))
        page = doc_service.list_documents(no_owner=True)
        assert [i["id"] for i in page["items"]] == ["gov-none"]

    def test_get_document_attaches_citations_from_linked_entry(self, doc_repo, entry_service,
                                                               doc_service):
        doc_repo.upsert(_doc("gov-detail", "退货率口径", source_ref=SOURCE_REF))
        entry = entry_service.create(
            title="退货率口径", content=RETURN_RATE, owner="u-owner",
            citations=[{"kind": "metric", "ref": "metric:order_return_rate@2026Q3"}],
        )
        _link_entry_to_source_ref(entry_service, entry.id, SOURCE_REF)

        payload = doc_service.get_document("gov-detail")
        assert [c["ref"] for c in payload["citations"]] == ["metric:order_return_rate@2026Q3"]
        assert "content" not in payload

    def test_get_unknown_document_raises_404(self, doc_service):
        with pytest.raises(ApiError) as excinfo:
            doc_service.get_document("gov-missing")
        assert excinfo.value.error_code == "DOC_NOT_FOUND"
        assert excinfo.value.status_code == 404
