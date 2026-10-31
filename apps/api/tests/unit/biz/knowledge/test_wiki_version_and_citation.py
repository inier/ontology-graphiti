"""版本快照与引用图服务测试（AC-05 / AC-06 / AC-10 的图侧）。

引用口径（`normalize_ref`）必须与治理校验（AC-11）一致，这里正反都验证。
"""

from __future__ import annotations

import pytest

from odap.common.api_errors import ApiError

SUPPLY_CONTENT = "供应商履约率 = 按期交付批次 / 总交付批次，按供应商维度聚合。"


class TestVersionHistory:
    def test_versions_ordered_latest_first(self, entry_service, version_service):
        entry = entry_service.create(title="履约率口径", content=SUPPLY_CONTENT, owner="u-owner")
        entry_service.update(entry.id, patch={"content": SUPPLY_CONTENT + " 补充：不含样机批次。"})
        versions = version_service.list_versions(entry.id)
        assert [v["change_note"] for v in versions][0] == "update content"
        assert len(versions) == 2
        # 快照内容互不覆盖（不可变追加）
        assert versions[0]["content"] != versions[1]["content"]

    def test_count_matches_snapshots(self, entry_service, version_service):
        entry = entry_service.create(title="履约率口径", content=SUPPLY_CONTENT, owner="u-owner")
        entry_service.publish(entry.id)
        entry_service.archive(entry.id)
        assert version_service.count(entry.id) == 3

    def test_snapshot_has_no_update_entry_point(self):
        from odap.biz.knowledge.wiki.repositories.version_repo import WikiVersionRepository

        assert not hasattr(WikiVersionRepository, "update")
        assert not hasattr(WikiVersionRepository, "delete")


class TestRefNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("doc:kb/123#chunk-4", "kb/123"),
            ("entry:doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A", "doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A"),
            ("wiki:docs/02-architecture/x.md", "docs/02-architecture/x.md"),
            ("repo:docs/02-architecture/x.md", "docs/02-architecture/x.md"),
            ("  docs/README.md  ", "docs/README.md"),
        ],
    )
    def test_normalize_ref(self, raw, expected):
        from odap.biz.knowledge.wiki.services.citation_service import normalize_ref

        assert normalize_ref(raw) == expected

    def test_ref_targets_entry_by_id_and_source_ref(self):
        from odap.biz.knowledge.wiki.services.citation_service import ref_targets_entry

        assert ref_targets_entry("entry:doc-01JABC", "doc-01JABC", None) is True
        assert ref_targets_entry("doc:02-architecture/x.md", "doc-01JABC",
                                 "repo:docs/02-architecture/x.md") is True
        assert ref_targets_entry("doc:02-architecture/y.md", "doc-01JABC",
                                 "repo:docs/02-architecture/x.md") is False
        assert ref_targets_entry("", "doc-01JABC", None) is False

    def test_parse_citations_rejects_invalid_kind(self):
        from odap.biz.knowledge.wiki.services.citation_service import parse_citations

        with pytest.raises(ApiError) as excinfo:
            parse_citations([{"kind": "email", "ref": "x@y"}])
        assert excinfo.value.status_code == 400
        assert excinfo.value.error_code == "WIKI_CITATION_INVALID"


class TestReferenceGraph:
    def test_outgoing_and_incoming_both_visible(self, entry_service, citation_service):
        target = entry_service.create(
            title="订单退货率口径", content="退货率 = 退货订单数 / 成交订单数。", owner="u-owner"
        )
        source = entry_service.create(
            title="季度经营复盘",
            content="本季度退货率恶化，详见订单退货率口径。",
            owner="u-owner",
            citations=[{"kind": "doc", "ref": f"entry:{target.id}"}],
        )

        graph = citation_service.build_graph(source.id)
        assert [c.ref for c in graph.outgoing] == [f"entry:{target.id}"]
        assert ("cites", source.id, target.id) in {(l.kind, l.from_id, l.to_id) for l in graph.links}

        reverse = citation_service.build_graph(target.id)
        assert [c.ref for c in reverse.incoming] == [f"entry:{target.id}"]
        assert any(l.from_id == source.id and l.to_id == target.id and l.kind == "cites"
                   for l in reverse.links)
        node_ids = {n.id for n in reverse.nodes}
        assert {source.id, target.id} <= node_ids

    def test_supersede_chain_appears_as_edges(self, entry_service, citation_service):
        old = entry_service.create(
            title="退货率口径（旧）", content="旧口径：按发货日期归集。", owner="u-owner"
        )
        new = entry_service.create(
            title="退货率口径（新）", content="新口径：按签收日期归集。", owner="u-owner"
        )
        entry_service.publish(old.id)
        entry_service.update(old.id, patch={"status": "superseded"})
        entry_service.entries.update(old.id, {"superseded_by": new.id})
        entry_service.entries.update(new.id, {"supersedes": [old.id]})

        graph = citation_service.build_graph(new.id)
        assert ("supersedes", old.id, new.id) in {
            (l.kind, l.from_id, l.to_id) for l in graph.links
        }

    def test_graph_for_unknown_entry_raises_404(self, citation_service):
        with pytest.raises(ApiError) as excinfo:
            citation_service.build_graph("doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A")
        assert excinfo.value.error_code == "WIKI_ENTRY_NOT_FOUND"
        assert excinfo.value.status_code == 404

    def test_non_doc_citation_is_kept_but_not_expanded(self, entry_service, citation_service):
        entry = entry_service.create(
            title="退货率指标定义",
            content="退货率 = 退货订单数 / 成交订单数。",
            owner="u-owner",
            citations=[{"kind": "metric", "ref": "metric:order_return_rate@2026Q3"}],
        )
        graph = citation_service.build_graph(entry.id)
        assert [c.kind.value for c in graph.outgoing] == ["metric"]
        assert graph.links == []  # 指标引用不进文档引用图（避免伪造跨域节点）
