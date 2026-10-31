"""Ingestor 端口化（P0-2）单元测试。

覆盖三层契约：
1. 规范化层：``canonical_text`` / ``hash_text`` / ``build_source_uri``
   必须稳定、可复现、不猜测；
2. 注册表层：source_type 冲突拒绝、分组列表与注册结果同源；
3. 门面接线层：未知来源显式报错、契约校验失败不再静默放行、
   成功与失败都要携带 source_uri/content_hash/watermark。
"""

from __future__ import annotations

import asyncio

import pytest

from odap.biz.data.ingest.ports.ingestor import (
    DOCUMENT_DRIVEN,
    EVENT_DRIVEN,
    ExtractionMode,
    IngestRequest,
    RawPayload,
    SourceCategory,
    build_normalized_doc,
    canonical_text,
    hash_text,
)
from odap.biz.data.ingest.registry import (
    FacadeIngestor,
    IngestorRegistry,
    build_source_uri,
)
from odap.biz.data.ingest.unified_ingest_facade import (
    EntityTypeValidationError,
    UnifiedIngestFacade,
)


# ---------------------------------------------------------------------------
# 规范化层
# ---------------------------------------------------------------------------

class TestCanonicalText:
    def test_str_is_returned_verbatim(self):
        # 首尾空白属于内容，裁剪会让「仅空白变更」在指纹里消失
        assert canonical_text("  a\n") == "  a\n"

    def test_dict_is_key_order_independent(self):
        assert canonical_text({"b": 1, "a": 2}) == canonical_text({"a": 2, "b": 1})

    def test_dict_is_stable_for_unicode(self):
        assert canonical_text({"名称": "红方"}) == '{"名称":"红方"}'

    def test_bytes_are_decoded_as_utf8(self):
        assert canonical_text("中文".encode("utf-8")) == "中文"

    def test_invalid_utf8_bytes_raise_instead_of_replacing(self):
        with pytest.raises(UnicodeDecodeError):
            canonical_text(b"\xff\xfe\x00")

    def test_none_becomes_empty_string(self):
        assert canonical_text(None) == ""


class TestHashText:
    def test_same_text_same_hash(self):
        assert hash_text("abc") == hash_text("abc")

    def test_whitespace_change_changes_hash(self):
        assert hash_text("a b") != hash_text("a  b")

    def test_hash_is_sha256_hex(self):
        assert hash_text("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )


class TestBuildSourceUri:
    def test_prefers_explicit_source_uri(self):
        assert build_source_uri("url", {"source_uri": "s3://x", "url": "http://y"}) == "s3://x"

    def test_falls_back_to_url(self):
        assert build_source_uri("url", {"url": "https://example.com/a"}) == "https://example.com/a"

    def test_scoped_natural_key(self):
        assert build_source_uri("news", {"query": "红海航运"}) == "news:红海航运"

    def test_sensor_uses_sensor_id(self):
        assert build_source_uri("sensor", {"sensor_id": "s-1"}) == "sensor:s-1"

    def test_empty_when_nothing_to_locate(self):
        assert build_source_uri("manual", {}) == ""


class TestBuildNormalizedDoc:
    def test_hash_and_len_are_utf8_based(self):
        raw = RawPayload(source_type="url", source_uri="https://x", content="红方",
                         fetched_at="2026-10-30T00:00:00+00:00")
        doc = build_normalized_doc(raw, workspace_id="ws1")
        assert doc.content_hash == hash_text("红方")
        assert doc.byte_len == len("红方".encode("utf-8")) == 6
        assert doc.workspace_id == "ws1"
        # 未显式给 watermark 时取抓取时间
        assert doc.watermark == "2026-10-30T00:00:00+00:00"

    def test_explicit_watermark_wins(self):
        raw = RawPayload(source_type="url", source_uri="u", content="x",
                         watermark="wm-7", fetched_at="2026-10-30T00:00:00+00:00")
        assert build_normalized_doc(raw).watermark == "wm-7"

    def test_metadata_excludes_body(self):
        raw = RawPayload(source_type="url", source_uri="u", content="secret-body")
        meta = build_normalized_doc(raw).as_metadata()
        assert "text" not in meta
        assert meta["source_uri"] == "u"
        assert meta["content_hash"] == hash_text("secret-body")


# ---------------------------------------------------------------------------
# 注册表层
# ---------------------------------------------------------------------------

def _port(category, types, handler=None):
    async def _default(source_type, **kwargs):
        return {"status": "ok", "source_type": source_type}

    return FacadeIngestor(
        category=category,
        source_types=frozenset(types),
        handler=handler or _default,
    )


class TestIngestorRegistry:
    def test_duplicate_source_type_rejected(self):
        reg = IngestorRegistry()
        reg.register(_port(DOCUMENT_DRIVEN, {"url", "news"}))
        with pytest.raises(ValueError, match="duplicate ingest source_type 'url'"):
            reg.register(_port(DOCUMENT_DRIVEN, {"url"}))

    def test_rejected_registration_leaves_previous_intact(self):
        reg = IngestorRegistry()
        first = _port(DOCUMENT_DRIVEN, {"url", "news"})
        reg.register(first)
        with pytest.raises(ValueError):
            reg.register(_port(EVENT_DRIVEN, {"webhook", "url"}))
        assert reg.resolve("url") is first
        assert reg.resolve("webhook") is None

    def test_supported_groups_follow_registration(self):
        reg = IngestorRegistry()
        reg.register(_port(DOCUMENT_DRIVEN, {"json", "url"}))
        reg.register(_port(EVENT_DRIVEN, {"webhook"}))
        assert reg.supported() == {
            DOCUMENT_DRIVEN: ["json", "url"],
            EVENT_DRIVEN: ["webhook"],
        }

    def test_unknown_category_rejected(self):
        with pytest.raises(ValueError, match="unknown ingest category"):
            _port("side_channel", {"x"})

    def test_empty_source_types_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _port(DOCUMENT_DRIVEN, set())


# ---------------------------------------------------------------------------
# 门面接线层
# ---------------------------------------------------------------------------

class TestFacadeRouting:
    def test_registry_covers_legacy_category_constants(self):
        facade = UnifiedIngestFacade()
        supported = facade.get_supported_source_types()
        assert set(supported[DOCUMENT_DRIVEN]) == set(SourceCategory.DOCUMENT_DRIVEN)
        assert set(supported[EVENT_DRIVEN]) == set(SourceCategory.EVENT_DRIVEN)

    def test_unknown_source_lists_supported(self):
        facade = UnifiedIngestFacade()
        result = asyncio.run(facade.ingest("nope"))
        assert result["status"] == "error"
        assert "Unknown source type: nope" in result["message"]
        assert "url" in result["supported_source_types"]
        assert "webhook" in result["supported_source_types"]

    def test_every_supported_type_resolves(self):
        facade = UnifiedIngestFacade()
        for category, types in facade.get_supported_source_types().items():
            for source_type in types:
                assert facade._registry.resolve(source_type) is not None, source_type

    def test_contract_validation_failure_is_explicit(self):
        facade = UnifiedIngestFacade()

        class _BrokenRegistry:
            @property
            def ontology_service(self):
                raise RuntimeError("ontology service down")

        facade._type_registry = _BrokenRegistry()
        result = asyncio.run(facade.ingest("url", url="https://x", ontology_id="ont-1"))
        assert result["status"] == "error"
        assert "摄入契约校验失败" in result["message"]
        assert "ontology service down" in result["message"]

    def test_missing_ontology_is_explicit(self):
        facade = UnifiedIngestFacade()

        class _Registry:
            class ontology_service:  # noqa: N801 - 模拟门面期望的属性形态
                @staticmethod
                def get_ontology(oid):
                    return {"status": "error"}

        facade._type_registry = _Registry()
        result = asyncio.run(facade.ingest("url", url="https://x", ontology_id="ont-miss"))
        assert result["status"] == "error"
        assert "本体不存在" in result["message"]

    def test_validate_entity_type_raises_when_service_unavailable(self):
        facade = UnifiedIngestFacade()

        class _BrokenRegistry:
            @staticmethod
            def list_object_types(oid):
                raise RuntimeError("db down")

        facade._type_registry = _BrokenRegistry()
        with pytest.raises(EntityTypeValidationError, match="db down"):
            facade.validate_entity_type("ont-1", "Unit")

    def test_validate_entity_type_reports_undefined_type(self):
        facade = UnifiedIngestFacade()

        class _Registry:
            @staticmethod
            def list_object_types(oid):
                return {"object_types": [{"name": "Unit", "type_id": "T-Unit"}]}

        facade._type_registry = _Registry()
        assert facade.validate_entity_type("ont-1", "Unit") == {"valid": True, "type_id": "T-Unit"}
        miss = facade.validate_entity_type("ont-1", "Ship")
        assert miss["valid"] is False


class TestFacadeMetadataPassthrough:
    def test_success_result_carries_metadata(self):
        facade = UnifiedIngestFacade()

        class _Svc:
            @staticmethod
            async def ingest_from_url(**kwargs):
                return "rec-1"

        facade._ingest_service = _Svc()
        result = asyncio.run(facade.ingest("url", url="https://example.com/a"))
        assert result["status"] == "ok"
        assert result["source_uri"] == "https://example.com/a"
        assert result["content_hash"] == hash_text("")
        assert result["watermark"]

    def test_error_result_also_carries_metadata(self):
        facade = UnifiedIngestFacade()

        class _Svc:
            @staticmethod
            async def ingest_from_url(**kwargs):
                raise RuntimeError("connection failed")

        facade._ingest_service = _Svc()
        result = asyncio.run(facade.ingest("url", url="https://example.com/a"))
        assert result["status"] == "error"
        assert "connection failed" in result["message"]
        # 失败时同样要能定位「哪一份输入坏了」
        assert result["source_uri"] == "https://example.com/a"
        assert result["content_hash"] == hash_text("")

    def test_handler_returning_non_dict_is_rejected(self):
        async def _bad(source_type, **kwargs):
            return "rec-1"

        port = _port(DOCUMENT_DRIVEN, {"url"}, handler=_bad)
        with pytest.raises(TypeError, match="expected dict"):
            asyncio.run(port.ingest(IngestRequest(source_type="url", kwargs={"url": "u"})))

    def test_facade_ingestor_does_not_overwrite_handler_keys(self):
        async def _handler(source_type, **kwargs):
            return {"status": "ok", "content_hash": "handler-owned"}

        port = _port(DOCUMENT_DRIVEN, {"url"}, handler=_handler)
        result = asyncio.run(port.ingest(IngestRequest(source_type="url", kwargs={"text": "x"})))
        assert result["content_hash"] == "handler-owned"


class TestExtractionModeDefaults:
    def test_default_mode_is_constrained(self):
        req = IngestRequest(source_type="url", kwargs={})
        assert req.extraction_mode == ExtractionMode.CONSTRAINED

    def test_exploratory_mode_skips_contract_check(self):
        facade = UnifiedIngestFacade()

        class _ExplodingRegistry:
            @property
            def ontology_service(self):
                raise AssertionError("exploratory 不应触发契约校验")

        facade._type_registry = _ExplodingRegistry()

        class _Svc:
            @staticmethod
            async def ingest_from_manual(**kwargs):
                return "rec-2"

        facade._ingest_service = _Svc()
        result = asyncio.run(facade.ingest(
            "manual", form_data={"a": 1}, ontology_id="ont-1",
            extraction_mode=ExtractionMode.EXPLORATORY,
        ))
        assert result["status"] == "ok"
