"""去重候选服务测试（AC-14）。

判重口径：同 content_hash 相似度恒 1.0；embedding 相似度本轮不实现，
因此不允许出现「估算相似度」的候选（避免伪造数值）。
"""

from __future__ import annotations

import pytest

SAME_BODY = "退货率 = 退货订单数 / 成交订单数（按签收日期归集）。"
OTHER_BODY = "履约率 = 按期交付批次 / 总交付批次（按供应商维度聚合）。"


class TestDedupeCandidates:
    def test_same_hash_grouped_with_canonical_earliest(self, entry_service, dedupe_service):
        first = entry_service.create(title="退货率口径", content=SAME_BODY, owner="u-owner")
        second = entry_service.create(title="退货率口径（副本）", content=SAME_BODY, owner="u-owner")
        entry_service.create(title="履约率口径", content=OTHER_BODY, owner="u-owner")

        candidates = dedupe_service.list_candidates()
        assert len(candidates) == 1
        candidate = candidates[0]
        assert set(candidate.doc_ids) == {first.id, second.id}
        assert candidate.similarity == 1.0
        assert candidate.reason == "same_hash"
        assert candidate.canonical_id == first.id  # 最早创建者为真相源

    def test_threshold_filters_lower_similarity(self, entry_service, dedupe_service):
        entry_service.create(title="退货率口径", content=SAME_BODY, owner="u-owner")
        entry_service.create(title="退货率口径（副本）", content=SAME_BODY, owner="u-owner")
        assert dedupe_service.list_candidates(threshold=1.0) != []
        assert dedupe_service.list_candidates(threshold=0.99) != []

    def test_invalid_threshold_raises(self, dedupe_service):
        with pytest.raises(ValueError) as excinfo:
            dedupe_service.list_candidates(threshold=1.2)
        assert "[0,1]" in str(excinfo.value)

    def test_unique_documents_produce_no_candidates(self, entry_service, dedupe_service):
        entry_service.create(title="退货率口径", content=SAME_BODY, owner="u-owner")
        entry_service.create(title="履约率口径", content=OTHER_BODY, owner="u-owner")
        assert dedupe_service.list_candidates() == []

    def test_repo_docs_and_entries_are_compared_together(self, sync_service, entry_service,
                                                         dedupe_service, repo_root):
        (repo_root / "docs" / "02-architecture" / "return-rate.md").write_text(
            "---\ntitle: 退货率口径\nowner: u-owner\n---\n\n" + SAME_BODY, encoding="utf-8"
        )
        sync_service.import_from_repo("docs/02-architecture/return-rate.md", actor_id="u-owner")
        entry_service.create(title="退货率口径（手工副本）", content=SAME_BODY, owner="u-owner")

        candidates = dedupe_service.list_candidates()
        assert len(candidates) == 1
        # 一条来自仓库纳管文档、一条来自 wiki 条目 -> 跨来源也要能合并
        assert len(candidates[0].doc_ids) == 2
