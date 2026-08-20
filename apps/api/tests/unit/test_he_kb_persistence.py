"""Iter 2.1 (ADR-074): HE Knowledge Abstract persistence tests.

Tests cover:
- HEAdapter.feed_to_kb(): incrementally feeds text to persistent KA
  - Creates new KA when kb_path/metadata.json doesn't exist
  - Loads + feeds existing KA when metadata.json exists
  - Returns False on empty text / failure
  - Returns True on success
- HEAdapter.load_from_kb(): reads accumulated KA state
  - Returns None when KA doesn't exist
  - Returns normalized dict when KA exists
  - Reads template/lang from metadata.json
- get_kb_path(): resolves kb path by workspace + ontology
  - Format: data/he_kb/{workspace_id}/{ontology_id}/
  - Respects he.kb_base_path config override
- ExtractService.extract_from_document: kb-backed extraction
  - Calls feed_to_kb + load_from_kb
  - Sets degradation flags on failure
  - Returns status="ok" with accumulated state

All tests mock HEAdapter internals (Template.create, ka.load, ka.feed_text,
ka.dump). No real LLM/embedder calls.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


# ---------------------------------------------------------------------------
# get_kb_path
# ---------------------------------------------------------------------------

class TestGetKbPath:
    def test_format_uses_workspace_and_ontology(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import get_kb_path
        path = get_kb_path("ws1", "ont1")
        # Path components: base / workspace / ontology
        assert path.endswith(os.path.join("ws1", "ont1"))

    def test_default_workspace_when_empty(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import get_kb_path
        path = get_kb_path("", "ont1")
        assert "default" in path
        assert "ont1" in path

    def test_default_ontology_when_empty(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import get_kb_path
        path = get_kb_path("ws1", "")
        assert "ws1" in path
        assert "default" in path

    def test_respects_config_override(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import get_kb_path
        with patch("odap.biz.data.hyper_extract.impl.he_adapter.get_config") as mock_cfg:
            mock_cfg.return_value = "/custom/base"
            path = get_kb_path("ws1", "ont1")
            assert path.startswith("/custom/base")
            assert path.endswith(os.path.join("ws1", "ont1"))


# ---------------------------------------------------------------------------
# HEAdapter.feed_to_kb
# ---------------------------------------------------------------------------

class TestFeedToKb:
    @pytest.fixture
    def adapter(self):
        """HEAdapter with mocked HE availability and client factories."""
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, '__init__', lambda self: None):
            adj = HEAdapter()
        adj._available = True
        adj._Template = MagicMock()
        adj._create_llm_client = MagicMock(return_value=MagicMock())
        adj._create_embedder = MagicMock(return_value=None)
        adj._embedder_cache = None
        return adj

    def test_creates_new_ka_when_metadata_missing(self, adapter, tmp_path):
        """When kb_path/metadata.json doesn't exist, create new KA + dump."""
        kb_path = str(tmp_path / "new_kb")
        mock_ka = MagicMock()
        adapter._Template.create.return_value = mock_ka

        result = adapter.feed_to_kb(kb_path, "some new text")

        assert result is True
        # Directory created
        assert (tmp_path / "new_kb").exists()
        # KA created via Template.create
        adapter._Template.create.assert_called_once()
        # feed_text called with the new text
        mock_ka.feed_text.assert_called_once_with("some new text")
        # dump called to persist
        mock_ka.dump.assert_called_once_with(str(tmp_path / "new_kb"))
        # load NOT called (new KA)
        mock_ka.load.assert_not_called()

    def test_loads_existing_ka_when_metadata_present(self, adapter, tmp_path):
        """When kb_path/metadata.json exists, load KA then feed + dump."""
        kb_dir = tmp_path / "existing_kb"
        kb_dir.mkdir()
        # Write metadata.json so HEAdapter treats it as existing KA
        (kb_dir / "metadata.json").write_text(
            json.dumps({"template": "general/graph", "lang": "zh"}),
            encoding="utf-8",
        )
        mock_ka = MagicMock()
        adapter._Template.create.return_value = mock_ka

        result = adapter.feed_to_kb(str(kb_dir), "additional text")

        assert result is True
        # load called first (accumulate)
        mock_ka.load.assert_called_once_with(str(kb_dir))
        # then feed_text
        mock_ka.feed_text.assert_called_once_with("additional text")
        # then dump
        mock_ka.dump.assert_called_once_with(str(kb_dir))

    def test_returns_false_on_empty_text(self, adapter, tmp_path):
        """Empty text should return False without creating KA."""
        kb_path = str(tmp_path / "kb")
        result = adapter.feed_to_kb(kb_path, "")
        assert result is False
        adapter._Template.create.assert_not_called()

    def test_returns_false_on_whitespace_only_text(self, adapter, tmp_path):
        """Whitespace-only text should return False."""
        kb_path = str(tmp_path / "kb")
        result = adapter.feed_to_kb(kb_path, "   \n  \t  ")
        assert result is False
        adapter._Template.create.assert_not_called()

    def test_returns_false_on_feed_exception(self, adapter, tmp_path):
        """When ka.feed_text raises, feed_to_kb returns False (no raise)."""
        kb_path = str(tmp_path / "kb")
        mock_ka = MagicMock()
        mock_ka.feed_text.side_effect = RuntimeError("LLM timeout")
        adapter._Template.create.return_value = mock_ka

        result = adapter.feed_to_kb(kb_path, "some text")
        assert result is False

    def test_raises_when_he_unavailable(self, tmp_path):
        """When HE is not available, feed_to_kb raises RuntimeError."""
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, '__init__', lambda self: None):
            adj = HEAdapter()
        adj._available = False

        with pytest.raises(RuntimeError, match="hyperextract"):
            adj.feed_to_kb(str(tmp_path / "kb"), "text")

    def test_passes_template_config_to_create(self, adapter, tmp_path):
        """Explicit template config overrides default."""
        kb_path = str(tmp_path / "kb")
        mock_ka = MagicMock()
        adapter._Template.create.return_value = mock_ka

        adapter.feed_to_kb(
            kb_path, "text",
            template={"template_path": "/custom/tpl.yaml", "language": "en"},
        )

        # Template.create called with the custom source + language
        args, kwargs = adapter._Template.create.call_args
        assert "/custom/tpl.yaml" in (args + tuple(kwargs.values()))
        assert "en" in (args + tuple(kwargs.values()))


# ---------------------------------------------------------------------------
# HEAdapter.load_from_kb
# ---------------------------------------------------------------------------

class TestLoadFromKb:
    @pytest.fixture
    def adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, '__init__', lambda self: None):
            adj = HEAdapter()
        adj._available = True
        adj._Template = MagicMock()
        adj._create_llm_client = MagicMock(return_value=MagicMock())
        adj._create_embedder = MagicMock(return_value=None)
        adj._embedder_cache = None
        return adj

    def test_returns_none_when_kb_not_found(self, adapter, tmp_path):
        """When kb_path/metadata.json doesn't exist, return None."""
        result = adapter.load_from_kb(str(tmp_path / "nonexistent"))
        assert result is None
        adapter._Template.create.assert_not_called()

    def test_returns_normalized_state_when_kb_exists(self, adapter, tmp_path):
        """When KA exists, load and return normalized dict."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "metadata.json").write_text(
            json.dumps({"template": "general/graph", "lang": "zh"}),
            encoding="utf-8",
        )
        mock_ka = MagicMock()
        mock_ka.nodes = [
            MagicMock(name="entity1", type="system", description="d1", properties={}),
        ]
        mock_ka.edges = []
        adapter._Template.create.return_value = mock_ka

        result = adapter.load_from_kb(str(kb_dir))

        assert result is not None
        assert "entities" in result
        assert "relations" in result
        assert len(result["entities"]) == 1
        mock_ka.load.assert_called_once_with(str(kb_dir))

    def test_returns_none_on_load_exception(self, adapter, tmp_path):
        """When ka.load raises, return None."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "metadata.json").write_text(
            json.dumps({"template": "general/graph", "lang": "zh"}),
            encoding="utf-8",
        )
        mock_ka = MagicMock()
        mock_ka.load.side_effect = RuntimeError("corrupt KA")
        adapter._Template.create.return_value = mock_ka

        result = adapter.load_from_kb(str(kb_dir))
        assert result is None

    def test_reads_template_and_lang_from_metadata(self, adapter, tmp_path):
        """Template.create receives template/lang from metadata.json."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "metadata.json").write_text(
            json.dumps({"template": "finance/event_timeline", "lang": "en"}),
            encoding="utf-8",
        )
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        adapter._Template.create.return_value = mock_ka

        adapter.load_from_kb(str(kb_dir))

        args, kwargs = adapter._Template.create.call_args
        all_args = args + tuple(kwargs.values())
        assert "finance/event_timeline" in all_args
        assert "en" in all_args

    def test_falls_back_to_defaults_on_bad_metadata(self, adapter, tmp_path):
        """Malformed metadata.json falls back to general/graph + zh."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "metadata.json").write_text("not valid json", encoding="utf-8")
        mock_ka = MagicMock()
        mock_ka.nodes = []
        mock_ka.edges = []
        adapter._Template.create.return_value = mock_ka

        result = adapter.load_from_kb(str(kb_dir))
        # Should still attempt load with defaults
        assert result is not None
        args, kwargs = adapter._Template.create.call_args
        all_args = args + tuple(kwargs.values())
        assert "general/graph" in all_args
        assert "zh" in all_args

    def test_raises_when_he_unavailable(self, tmp_path):
        """When HE is not available, load_from_kb raises RuntimeError."""
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        with patch.object(HEAdapter, '__init__', lambda self: None):
            adj = HEAdapter()
        adj._available = False

        with pytest.raises(RuntimeError, match="hyperextract"):
            adj.load_from_kb(str(tmp_path / "kb"))


# ---------------------------------------------------------------------------
# ExtractService.extract_from_document — kb-backed path
# ---------------------------------------------------------------------------

class TestExtractFromDocumentKbBacked:
    """Iter 2.1: extract_from_document uses feed_to_kb + load_from_kb."""

    @pytest.fixture
    def service(self):
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        adapter = MagicMock()
        adapter.feed_to_kb.return_value = True
        adapter.load_from_kb.return_value = {
            "entities": [{"name": "ent1", "type": "system"}],
            "relations": [],
        }
        template_engine = MagicMock()
        template_engine.assess.return_value = {
            "candidates": [], "best_score": 0.0,
            "threshold": 0.5, "needs_custom": False, "settled_used": False,
        }
        ontology_mapper = MagicMock()
        ontology_mapper.merge_and_map.return_value = {
            "entities": [{"name": "ent1"}],
            "object_types": [], "link_types": [],
            "action_types": [], "rule_types": [], "process_types": [],
        }
        storage = MagicMock()
        storage.create_session.return_value = {"session_id": "sess-1"}
        storage.update_session = MagicMock()
        writer = MagicMock()
        provenance_tracker = MagicMock()

        svc = ExtractService(
            adapter=adapter,
            template_engine=template_engine,
            ontology_mapper=ontology_mapper,
            storage=storage,
            writer=writer,
            provenance_tracker=provenance_tracker,
        )
        return svc, adapter

    @pytest.mark.asyncio
    async def test_calls_feed_to_kb_with_resolved_path(self, service, tmp_path):
        """extract_from_document must call adapter.feed_to_kb(kb_path, full_text)."""
        svc, adapter = service
        # Create a temp file to parse
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("这是测试文档内容。", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "he_kb" / "ws1" / "ont1")):
            await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
                workspace_id="ws1",
            )

        adapter.feed_to_kb.assert_called_once()
        args, kwargs = adapter.feed_to_kb.call_args
        # First positional arg is kb_path
        kb_path_arg = args[0] if args else kwargs.get("kb_path")
        assert "ws1" in kb_path_arg
        assert "ont1" in kb_path_arg

    @pytest.mark.asyncio
    async def test_calls_load_from_kb_after_feed(self, service, tmp_path):
        """After feed_to_kb, extract_from_document must call load_from_kb."""
        svc, adapter = service
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("test content", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "kb")):
            await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
            )

        adapter.load_from_kb.assert_called_once()

    @pytest.mark.asyncio
    async def test_sets_degradation_flag_on_feed_failure(self, service, tmp_path):
        """When feed_to_kb returns False, kb_feed_failed flag is set."""
        svc, adapter = service
        adapter.feed_to_kb.return_value = False
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("content", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "kb")):
            result = await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
            )

        assert result["status"] == "ok"
        assert "kb_feed_failed" in result["degradation_flags"]

    @pytest.mark.asyncio
    async def test_sets_degradation_flag_on_load_failure(self, service, tmp_path):
        """When load_from_kb returns None, kb_load_failed flag is set."""
        svc, adapter = service
        adapter.load_from_kb.return_value = None
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("content", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "kb")):
            result = await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
            )

        assert "kb_load_failed" in result["degradation_flags"]

    @pytest.mark.asyncio
    async def test_returns_ok_with_accumulated_state(self, service, tmp_path):
        """On success, result includes accumulated entities from kb."""
        svc, adapter = service
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("content", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "kb")):
            result = await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
                workspace_id="ws1",
            )

        assert result["status"] == "ok"
        assert result["session_id"] == "sess-1"
        assert result["result"] is not None
        assert "entities" in result["result"]
        assert result["provenance_summary"]["kb_feed_ok"] is True
        assert result["provenance_summary"]["workspace_id"] == "ws1"

    @pytest.mark.asyncio
    async def test_empty_file_returns_error(self, service, tmp_path):
        """Empty file should return status=error."""
        svc, adapter = service
        doc_path = tmp_path / "empty.txt"
        doc_path.write_text("", encoding="utf-8")

        result = await svc.extract_from_document(
            ontology_id="ont1",
            file_path=str(doc_path),
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_ontology_returns_error(self, service, tmp_path):
        """Missing ontology_id should return status=error."""
        svc, adapter = service
        result = await svc.extract_from_document(
            ontology_id="",
            file_path=str(tmp_path / "doc.txt"),
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_passes_template_id_as_template_config(self, service, tmp_path):
        """When template_id is provided, it's passed to feed_to_kb as template_path."""
        svc, adapter = service
        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("content", encoding="utf-8")

        with patch("odap.biz.data.hyper_extract.services.extract_service.get_kb_path",
                    return_value=str(tmp_path / "kb")):
            await svc.extract_from_document(
                ontology_id="ont1",
                file_path=str(doc_path),
                template_id="general/event_timeline",
            )

        args, kwargs = adapter.feed_to_kb.call_args
        template_arg = kwargs.get("template") or (args[2] if len(args) > 2 else None)
        assert template_arg is not None
        assert template_arg.get("template_path") == "general/event_timeline"
        assert template_arg.get("language") == "zh"
