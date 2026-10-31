"""front-matter 解析/序列化测试（AC-15 / AC-16 的格式层）。

关键不变量：`parse(serialize(fm))` 不丢纳管字段；非法输入必须显式报错
（不静默丢字段 —— 否则导入会伪造「字段齐全」的假象）。
"""

from __future__ import annotations

import pytest

from odap.biz.knowledge.governance.services.frontmatter import (
    MANAGED_FIELDS,
    FrontMatterError,
    normalize_front_matter,
    parse_document,
    serialize_document,
)

BODY = (
    "# 订单退货率口径\n\n"
    "退货率 = 退货订单数 / 成交订单数，按签收日期归集。\n"
)

DOC = """---
id: doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A
title: 订单退货率口径
status: published
owner: u-data-owner
version: 1.2.0
source_ref: repo:docs/02-architecture/return-rate.md
superseded_by: null
supersedes:
  - doc-01J9ZK8P3Q7N2M4R5T6V7W8X9B
content_hash: sha256:abc123
last_verified: 2026-10-01
tags: [metric, order]
citations:
  - kind: metric
    ref: metric:order_return_rate@2026Q3
---

# 订单退货率口径
"""


class TestParse:
    def test_parse_returns_front_matter_and_body(self):
        front_matter, body = parse_document(DOC)
        assert front_matter["title"] == "订单退货率口径"
        assert front_matter["status"] == "published"
        assert front_matter["tags"] == ["metric", "order"]
        assert body.startswith("# 订单退货率口径")

    def test_document_without_front_matter_returns_empty_mapping(self):
        front_matter, body = parse_document(BODY)
        assert front_matter == {}
        assert body == BODY

    def test_none_input_raises(self):
        with pytest.raises(FrontMatterError):
            parse_document(None)

    def test_invalid_yaml_raises_with_reason(self):
        broken = "---\ntitle: 退货率口径\nowner: [未闭合\n---\n\n正文\n"
        with pytest.raises(FrontMatterError) as excinfo:
            parse_document(broken)
        assert "YAML" in str(excinfo.value)

    def test_non_mapping_root_raises(self):
        with pytest.raises(FrontMatterError) as excinfo:
            parse_document("---\n- 退货率口径\n- 履约率口径\n---\n\n正文\n")
        assert "映射" in str(excinfo.value)


class TestNormalize:
    def test_drops_unknown_fields_and_keeps_managed_order(self):
        normalized = normalize_front_matter(
            {"title": "退货率口径", "owner": "u-owner", "random_key": "应被丢弃"}
        )
        assert "random_key" not in normalized
        assert list(normalized) == ["title", "owner"]

    def test_supersedes_string_becomes_list(self):
        normalized = normalize_front_matter({"supersedes": "doc-01JABC"})
        assert normalized["supersedes"] == ["doc-01JABC"]

    def test_last_verified_truncated_to_date(self):
        normalized = normalize_front_matter({"last_verified": "2026-10-01T08:00:00+08:00"})
        assert normalized["last_verified"] == "2026-10-01"

    def test_citation_string_becomes_doc_reference(self):
        normalized = normalize_front_matter({"citations": "docs/02-architecture/x.md"})
        assert normalized["citations"] == [
            {"kind": "doc", "ref": "docs/02-architecture/x.md"}
        ]

    def test_invalid_citation_item_raises(self):
        with pytest.raises(FrontMatterError):
            normalize_front_matter({"citations": [{"no_ref": True}]})


class TestRoundTrip:
    def test_serialize_parse_preserves_all_managed_fields(self):
        front_matter, _body = parse_document(DOC)
        normalized = normalize_front_matter(front_matter)
        text = serialize_document(normalized, BODY)
        reparsed, body = parse_document(text)

        for field in MANAGED_FIELDS:
            if field in normalized:
                assert field in reparsed, field
        assert reparsed["title"] == normalized["title"]
        assert reparsed["supersedes"] == normalized["supersedes"]
        assert reparsed["citations"] == normalized["citations"]
        assert body.startswith("# 订单退货率口径")

    def test_serialize_emits_front_matter_block(self):
        text = serialize_document({"title": "退货率口径", "owner": "u-owner"}, BODY)
        assert text.startswith("---\n")
        assert "\n---\n\n" in text


GOVERNANCE_FM = """---
id: odap.l7.adr-095
status: active
owner: architect
version: '2.0'
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-095
"""


class TestGovernanceKeys:
    """`layer/concern/lifecycle/authority` 必须在纳管字段里。

    漏一个键的后果不是"少显示一栏"，而是 `serialize_document` 回写时**静默删掉**
    仓库侧元数据（policy `roundtrip_preserved_keys`，ADR-097 三元正交模型）。
    """

    def test_managed_fields_contain_governance_keys(self):
        for key in ("layer", "concern", "lifecycle", "authority"):
            assert key in MANAGED_FIELDS, key

    def test_normalize_keeps_governance_keys_as_strings(self):
        normalized = normalize_front_matter(parse_document(GOVERNANCE_FM)[0])
        assert normalized["layer"] == "L7"
        assert normalized["concern"] == "adr"
        assert normalized["lifecycle"] == "frozen"
        assert "authority" not in normalized  # 文档未显式给出就不造键

    def test_none_valued_governance_key_normalized_to_empty_string(self):
        normalized = normalize_front_matter({"layer": None, "concern": "adr"})
        assert normalized["layer"] == ""
        assert normalized["concern"] == "adr"

    def test_governance_keys_survive_serialize_parse(self):
        normalized = normalize_front_matter(parse_document(GOVERNANCE_FM)[0])
        reparsed, _body = parse_document(serialize_document(normalized, BODY))
        for key in ("layer", "concern", "lifecycle"):
            assert reparsed.get(key) == normalized[key], key

    def test_authority_key_passes_through_when_declared(self):
        normalized = normalize_front_matter({"status": "active", "authority": "authoritative"})
        reparsed, _body = parse_document(serialize_document(normalized, BODY))
        assert reparsed["authority"] == "authoritative"
