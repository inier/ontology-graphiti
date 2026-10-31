"""Wiki 条目服务测试（AC-01 / AC-02 / AC-03 / AC-04 / AC-07 / AC-08）。

真实业务语义数据：订单退货率、供应商履约率（不是 foo/bar）。
"""

from __future__ import annotations

import re

import pytest

from odap.common.api_errors import ApiError

TRACE_ULID = re.compile(r"^doc-[0-9A-HJKMNP-TV-Z]{26}$")

CONTENT = (
    "退货率口径：统计周期内退货订单数 / 成交订单数。"
    "口径以订单履约事实表为准，排除仅退款未发货的订单。"
)


class TestCreate:
    def test_create_returns_ulid_and_initial_version(self, entry_service):
        entry = entry_service.create(
            title="订单退货率口径说明",
            content=CONTENT,
            owner="u-data-owner",
            tags=["metric", "order"],
            workspace_id="ws-supply",
        )
        assert TRACE_ULID.match(entry.id), entry.id
        assert entry.version == "0.1.0"
        assert entry.status.value == "draft"
        assert entry.content_hash.startswith("sha256:")
        assert entry.workspace_id == "ws-supply"
        assert entry.last_verified is None

    def test_create_writes_baseline_snapshot(self, entry_service, version_service):
        entry = entry_service.create(title="履约率口径", content=CONTENT, owner="u-owner")
        versions = version_service.list_versions(entry.id)
        assert len(versions) == 1
        assert versions[0]["change_note"] == "create"
        assert versions[0]["version"] == "0.1.0"

    def test_missing_owner_raises_400_with_field(self, entry_service):
        with pytest.raises(ApiError) as excinfo:
            entry_service.create(title="退货率口径", content=CONTENT, owner="  ")
        assert excinfo.value.error_code == "WIKI_OWNER_REQUIRED"
        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == {"field": "owner"}

    def test_missing_title_and_content_are_distinct_codes(self, entry_service):
        with pytest.raises(ApiError) as title_err:
            entry_service.create(title=" ", content=CONTENT, owner="u-owner")
        assert title_err.value.error_code == "WIKI_TITLE_REQUIRED"
        with pytest.raises(ApiError) as content_err:
            entry_service.create(title="退货率口径", content="  ", owner="u-owner")
        assert content_err.value.error_code == "WIKI_CONTENT_REQUIRED"


class TestRead:
    def test_get_unknown_id_raises_not_found(self, entry_service):
        with pytest.raises(ApiError) as excinfo:
            entry_service.get("doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A")
        assert excinfo.value.error_code == "WIKI_ENTRY_NOT_FOUND"
        assert excinfo.value.status_code == 404

    def test_list_entries_paginates_and_filters(self, entry_service):
        for index in range(3):
            entry_service.create(
                title=f"退货率口径 v{index}", content=f"{CONTENT}#{index}", owner="u-owner"
            )
        page = entry_service.list_entries(page=1, limit=2)
        assert page["total"] == 3
        assert len(page["items"]) == 2
        assert page["hasMore"] is True

        filtered = entry_service.list_entries(q="退货率")
        assert filtered["total"] == 3

    def test_list_entries_rejects_unknown_status(self, entry_service):
        with pytest.raises(ApiError) as excinfo:
            entry_service.list_entries(status="在写")
        assert excinfo.value.error_code == "WIKI_INVALID_STATUS_TRANSITION"
        assert excinfo.value.status_code == 400


class TestUpdateAndOptimisticLock:
    def test_content_change_bumps_patch_version_and_snapshot(self, entry_service,
                                                             version_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        updated = entry_service.update(
            entry.id,
            patch={"content": CONTENT + "补充：退货率按签收日期归集。"},
            expected_version="0.1.0",
            actor_id="u-editor",
        )
        assert updated.version == "0.1.1"
        assert updated.content_hash != entry.content_hash
        notes = [v["change_note"] for v in version_service.list_versions(entry.id)]
        assert "update content" in notes

    def test_same_content_does_not_bump_version(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        updated = entry_service.update(entry.id, patch={"content": CONTENT})
        assert updated.version == "0.1.0"

    def test_stale_version_raises_conflict_with_detail(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        entry_service.update(entry.id, patch={"content": CONTENT + "v2"}, expected_version="0.1.0")
        with pytest.raises(ApiError) as excinfo:
            entry_service.update(entry.id, patch={"tags": ["x"]}, expected_version="0.1.0")
        assert excinfo.value.error_code == "WIKI_VERSION_CONFLICT"
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == {"expected": "0.1.0", "actual": "0.1.1"}

    def test_owner_can_be_reassigned(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-old")
        updated = entry_service.update(entry.id, patch={"owner": "u-new"})
        assert updated.owner == "u-new"


class TestPublishAndDuplicate:
    def test_publish_sets_published_and_last_verified(self, entry_service, version_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        published = entry_service.publish(entry.id, actor_id="u-owner")
        assert published.status.value == "published"
        assert published.last_verified is not None
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", published.last_verified)
        assert [v["change_note"] for v in version_service.list_versions(entry.id)][0] == "publish"

    def test_publish_duplicate_hash_is_rejected_with_conflict_id(self, entry_service, make_entry):
        first = make_entry("退货率口径", CONTENT)
        second = entry_service.create(title="退货率口径（副本）", content=CONTENT, owner="u-other")
        with pytest.raises(ApiError) as excinfo:
            entry_service.publish(second.id, actor_id="u-other")
        assert excinfo.value.error_code == "WIKI_DUPLICATE_CONTENT"
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail["conflicting_entry_id"] == first.id

    def test_draft_duplicate_is_allowed_until_publish(self, entry_service):
        entry_service.create(title="退货率口径 A", content=CONTENT, owner="u-owner")
        draft = entry_service.create(title="退货率口径 B", content=CONTENT, owner="u-owner")
        assert draft.status.value == "draft"


class TestArchiveSoftDelete:
    def test_archive_keeps_rows_and_versions(self, entry_service, version_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        archived = entry_service.archive(entry.id, actor_id="u-owner")
        assert archived.status.value == "archived"
        # 软删除：仍可读取，版本一条不少
        assert entry_service.get(entry.id).status.value == "archived"
        assert version_service.count(entry.id) >= 1

    def test_archived_entry_cannot_be_edited_or_published(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        entry_service.archive(entry.id)
        with pytest.raises(ApiError) as edit_err:
            entry_service.update(entry.id, patch={"title": "改名"})
        assert edit_err.value.error_code == "WIKI_INVALID_STATUS_TRANSITION"
        assert edit_err.value.status_code == 409
        with pytest.raises(ApiError) as publish_err:
            entry_service.publish(entry.id)
        assert publish_err.value.error_code == "WIKI_INVALID_STATUS_TRANSITION"

    def test_illegal_transition_draft_to_superseded(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        with pytest.raises(ApiError) as excinfo:
            entry_service.update(entry.id, patch={"status": "superseded"})
        assert excinfo.value.error_code == "WIKI_INVALID_STATUS_TRANSITION"
        assert excinfo.value.detail["from"] == "draft"
        assert excinfo.value.detail["to"] == "superseded"

    def test_review_then_publish_is_allowed(self, entry_service):
        entry = entry_service.create(title="退货率口径", content=CONTENT, owner="u-owner")
        reviewed = entry_service.update(entry.id, patch={"status": "review"})
        assert reviewed.status.value == "review"
        assert entry_service.publish(entry.id).status.value == "published"


class TestVersionBump:
    def test_bump_patch_rejects_non_semver(self):
        from odap.biz.knowledge.wiki.services.entry_service import bump_patch

        assert bump_patch("0.1.0") == "0.1.1"
        assert bump_patch("1.9.9") == "1.9.10"
        with pytest.raises(ApiError) as excinfo:
            bump_patch("v1")
        assert excinfo.value.error_code == "INTERNAL_ERROR"
