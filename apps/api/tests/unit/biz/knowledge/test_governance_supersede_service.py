"""supersede 链服务测试（AC-10）。

不变量：A 被 B 取代后 —— A.status=superseded、A.superseded_by=B、B.supersedes 含 A，
且 A 不得被删除（真相源链可追溯）。另测三道护栏：自取代 / 目标非法 / 成环。
"""

from __future__ import annotations

import pytest

from odap.common.api_errors import ApiError
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.biz.knowledge.models.common import DocStatus

OLD_BODY = "旧口径：退货率按发货日期归集。"
NEW_BODY = "新口径：退货率按签收日期归集（与财务口径一致）。"


def _doc(doc_id: str, title: str, body: str, *, source_ref=None,
         status=DocStatus.PUBLISHED) -> GovernedDoc:
    from odap.common.ids import content_hash

    return GovernedDoc(
        id=doc_id, title=title, status=status, owner="u-owner", version="1.0.0",
        source_ref=source_ref, content_hash=content_hash(body), content=body,
        last_verified="2026-10-01", role="be",
        created_at="2026-09-01T00:00:00+00:00", updated_at="2026-09-01T00:00:00+00:00",
    )


class TestSupersedeHappyPath:
    def test_both_directions_recorded_and_old_kept(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-old", "退货率口径（旧）", OLD_BODY))
        doc_repo.upsert(_doc("gov-new", "退货率口径（新）", NEW_BODY))

        result = supersede_service.supersede("gov-old", "gov-new")
        assert result.status == DocStatus.SUPERSEDED
        assert result.superseded_by == "gov-new"

        new_doc = doc_repo.get("gov-new")
        assert "gov-old" in new_doc.supersedes
        # 不得删除旧文档（真相源链完整）
        assert doc_repo.get("gov-old") is not None

    def test_mirrors_to_wiki_entry_by_source_ref(self, doc_repo, entry_service,
                                                 supersede_service):
        old_ref = "repo:docs/02-architecture/return-rate.md"
        new_ref = "repo:docs/02-architecture/return-rate-v2.md"
        doc_repo.upsert(_doc("gov-old", "退货率口径（旧）", OLD_BODY, source_ref=old_ref))
        doc_repo.upsert(_doc("gov-new", "退货率口径（新）", NEW_BODY, source_ref=new_ref))
        old_entry = entry_service.create(title="退货率口径（旧）", content=OLD_BODY,
                                         owner="u-owner")
        new_entry = entry_service.create(title="退货率口径（新）", content=NEW_BODY,
                                         owner="u-owner")
        entry_service.entries.update(old_entry.id, {"source_ref": old_ref})
        entry_service.entries.update(new_entry.id, {"source_ref": new_ref})

        supersede_service.supersede("gov-old", "gov-new")

        mirrored = entry_service.entries.get(old_entry.id)
        assert mirrored.status == DocStatus.SUPERSEDED
        assert mirrored.superseded_by == new_entry.id
        assert old_entry.id in entry_service.entries.get(new_entry.id).supersedes

    def test_idempotent_second_call_keeps_single_edge(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-old", "旧口径", OLD_BODY))
        doc_repo.upsert(_doc("gov-new", "新口径", NEW_BODY))
        supersede_service.supersede("gov-old", "gov-new")
        supersede_service.supersede("gov-old", "gov-new")
        assert doc_repo.get("gov-new").supersedes == ["gov-old"]


class TestSupersedeGuards:
    def test_self_supersede_rejected(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-a", "退货率口径", OLD_BODY))
        with pytest.raises(ApiError) as excinfo:
            supersede_service.supersede("gov-a", "gov-a")
        assert excinfo.value.error_code == "DOC_SUPERSEDE_SELF"
        assert excinfo.value.status_code == 400

    def test_empty_target_rejected(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-a", "退货率口径", OLD_BODY))
        with pytest.raises(ApiError) as excinfo:
            supersede_service.supersede("gov-a", "  ")
        assert excinfo.value.error_code == "DOC_SUPERSEDE_TARGET_INVALID"

    def test_missing_document_raises_404(self, supersede_service):
        with pytest.raises(ApiError) as excinfo:
            supersede_service.supersede("gov-none", "gov-other")
        assert excinfo.value.error_code == "DOC_NOT_FOUND"
        assert excinfo.value.status_code == 404

    def test_archived_target_rejected(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-old", "旧口径", OLD_BODY))
        doc_repo.upsert(_doc("gov-archived", "已归档口径", NEW_BODY,
                             status=DocStatus.ARCHIVED))
        with pytest.raises(ApiError) as excinfo:
            supersede_service.supersede("gov-old", "gov-archived")
        assert excinfo.value.error_code == "DOC_SUPERSEDE_TARGET_INVALID"
        assert excinfo.value.detail["target"] == "gov-archived"

    def test_cycle_rejected(self, doc_repo, supersede_service):
        doc_repo.upsert(_doc("gov-a", "旧口径", OLD_BODY))
        doc_repo.upsert(_doc("gov-b", "新口径", NEW_BODY))
        supersede_service.supersede("gov-a", "gov-b")
        # 反向再取代会成环：gov-a → gov-b → gov-a
        with pytest.raises(ApiError) as excinfo:
            supersede_service.supersede("gov-b", "gov-a")
        assert excinfo.value.error_code == "DOC_SUPERSEDE_CYCLE"
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail["origin"] == "gov-b"
