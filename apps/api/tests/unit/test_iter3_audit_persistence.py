"""Unit tests for Iter 3: Audit & Persistence.

Tests cover:
- Iter 3.1: RawDataStorage — upload_raw / download_raw / get_url
- Iter 3.1: OntologyDocument.raw_data_ref field
- Iter 3.1: NewsIngester raw data upload integration
- Iter 3.2: GraphitiAuditWriter — log_ingestion_audit / log_extraction_audit
- Iter 3.2: audit_helper.confirm_audit / query_audit
- Iter 3.2: NewsIngester #1 ingestion audit instrumentation
- Iter 3.2: ExtractService #2 extraction audit instrumentation

All tests use local fallback mode (no MinIO/Graphiti required).
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from odap.infra.storage.raw_data_storage import RawDataStorage, get_raw_data_storage
from odap.biz.core.ontology.design.schema.document import OntologyDocument


# ===========================================================================
# Iter 3.1: RawDataStorage
# ===========================================================================

class TestRawDataStorageUpload:
    """Test upload_raw with local fallback (MinIO not available in test env)."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a RawDataStorage with local fallback path."""
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = None  # Force local fallback
            s._fallback_base = str(tmp_path / "raw_data")
            os.makedirs(s._fallback_base, exist_ok=True)
            s._initialized = True
            return s

    def test_upload_raw_returns_raw_data_ref(self, storage):
        result = storage.upload_raw("ws1", "doc1", "hello world", "news_ingest")
        assert result["status"] == "success"
        assert result["raw_data_ref"] is not None
        assert result["raw_data_ref"].startswith("file://")
        assert result["storage_mode"] == "local_fallback"
        assert result["size"] == len("hello world")
        assert "checksum" in result

    def test_upload_raw_empty_text_skipped(self, storage):
        result = storage.upload_raw("ws1", "doc1", "", "news_ingest")
        assert result["status"] == "skipped"
        assert result["raw_data_ref"] is None

    def test_upload_raw_creates_nested_directory(self, storage, tmp_path):
        result = storage.upload_raw("ws1", "doc1", "data", "news_ingest")
        assert result["status"] == "success"
        # Verify file was created in nested path
        ref = result["raw_data_ref"]
        local_path = ref[len("file://"):]
        assert os.path.exists(local_path)

    def test_upload_raw_checksum_is_sha256(self, storage):
        result = storage.upload_raw("ws1", "doc1", "test", "news_ingest")
        # SHA-256 of "test" is 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
        assert result["checksum"] == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


class TestRawDataStorageDownload:
    """Test download_raw with local fallback."""

    @pytest.fixture
    def storage(self, tmp_path):
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = None
            s._fallback_base = str(tmp_path / "raw_data")
            os.makedirs(s._fallback_base, exist_ok=True)
            s._initialized = True
            return s

    def test_download_raw_roundtrip(self, storage):
        """Upload then download — data should match."""
        text = "采集的原始文本内容 test 123"
        upload = storage.upload_raw("ws1", "doc1", text, "news_ingest")
        assert upload["status"] == "success"

        download = storage.download_raw(upload["raw_data_ref"])
        assert download["status"] == "success"
        assert download["text"] == text
        assert download["size"] == len(text.encode("utf-8"))

    def test_download_raw_empty_ref(self, storage):
        result = storage.download_raw("")
        assert result["status"] == "error"

    def test_download_raw_unsupported_scheme(self, storage):
        result = storage.download_raw("ftp://example.com/file.txt")
        assert result["status"] == "error"
        assert "unsupported" in result["message"]

    def test_download_raw_nonexistent_file(self, storage):
        result = storage.download_raw("file:///nonexistent/path/file.txt")
        assert result["status"] == "error"


class TestRawDataStorageGetUrl:
    """Test get_url."""

    @pytest.fixture
    def storage(self, tmp_path):
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = None
            s._fallback_base = str(tmp_path / "raw_data")
            os.makedirs(s._fallback_base, exist_ok=True)
            s._initialized = True
            return s

    def test_get_url_local_fallback(self, storage):
        upload = storage.upload_raw("ws1", "doc1", "data", "news_ingest")
        result = storage.get_url(upload["raw_data_ref"])
        assert result["status"] == "success"
        assert result["url"] is None  # No presigned URL for local
        assert "local_path" in result

    def test_get_url_empty_ref(self, storage):
        result = storage.get_url("")
        assert result["status"] == "error"

    def test_get_url_unsupported_scheme(self, storage):
        result = storage.get_url("ftp://example.com/file.txt")
        assert result["status"] == "error"


class TestRawDataStorageAvailable:
    def test_available_false_when_minio_none(self, tmp_path):
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = None
            s._fallback_base = str(tmp_path)
            s._initialized = True
            assert s.available is False

    def test_available_false_when_minio_not_available(self, tmp_path):
        mock_minio = MagicMock()
        mock_minio.available = False
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = mock_minio
            s._fallback_base = str(tmp_path)
            s._initialized = True
            assert s.available is False

    def test_available_true_when_minio_ready(self, tmp_path):
        mock_minio = MagicMock()
        mock_minio.available = True
        with patch.object(RawDataStorage, "__new__", lambda cls, *a, **kw: object.__new__(cls)):
            s = RawDataStorage()
            s._minio = mock_minio
            s._fallback_base = str(tmp_path)
            s._initialized = True
            assert s.available is True


# ===========================================================================
# Iter 3.1: OntologyDocument.raw_data_ref
# ===========================================================================

class TestOntologyDocumentRawDataRef:
    def test_default_raw_data_ref_is_none(self):
        doc = OntologyDocument()
        assert doc.raw_data_ref is None

    def test_raw_data_ref_in_to_dict(self):
        doc = OntologyDocument(raw_data_ref="minio://bucket/key")
        d = doc.to_dict()
        assert d["raw_data_ref"] == "minio://bucket/key"

    def test_raw_data_ref_in_from_dict(self):
        data = {"doc_id": "test1", "raw_data_ref": "file:///tmp/test.txt"}
        doc = OntologyDocument.from_dict(data)
        assert doc.raw_data_ref == "file:///tmp/test.txt"

    def test_raw_data_ref_absent_in_from_dict_defaults_none(self):
        data = {"doc_id": "test2"}
        doc = OntologyDocument.from_dict(data)
        assert doc.raw_data_ref is None

    def test_roundtrip_preserves_raw_data_ref(self):
        doc = OntologyDocument(raw_data_ref="minio://odap-raw-data/ws1/doc1/file.txt")
        d = doc.to_dict()
        doc2 = OntologyDocument.from_dict(d)
        assert doc2.raw_data_ref == doc.raw_data_ref


# ===========================================================================
# Iter 3.1: NewsIngester raw data upload
# ===========================================================================

class TestNewsIngesterRawDataUpload:
    """Verify NewsIngester uploads raw data and sets raw_data_ref."""

    @pytest.fixture
    def ingester(self):
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        return NewsIngester()

    @pytest.mark.asyncio
    async def test_pending_doc_has_raw_data_ref(self, ingester):
        """When combined_text is provided, raw_data_ref should be set."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            docs = await ingester.ingest("query", workspace_id="ws1")
            assert len(docs) == 1
            # raw_data_ref should be set (local fallback in test env)
            assert docs[0].raw_data_ref is not None
            assert docs[0].raw_data_ref.startswith("file://")

    @pytest.mark.asyncio
    async def test_empty_text_no_raw_data_ref(self, ingester):
        """When search returns empty, combined_text is empty, no raw_data_ref."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            docs = await ingester.ingest("query", workspace_id="ws1")
            assert len(docs) == 1
            # Empty text → no raw_data_ref
            assert docs[0].raw_data_ref is None

    @pytest.mark.asyncio
    async def test_raw_data_ref_preserved_in_to_dict(self, ingester):
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            docs = await ingester.ingest("query", workspace_id="ws1")
            d = docs[0].to_dict()
            assert d["raw_data_ref"] is not None


# ===========================================================================
# Iter 3.2: GraphitiAuditWriter
# ===========================================================================

class TestGraphitiAuditWriter:
    """Test GraphitiAuditWriter — all methods should degrade gracefully when Graphiti unavailable."""

    @pytest.fixture
    def writer(self):
        from odap.infra.security.graphiti_audit_writer import GraphitiAuditWriter
        w = GraphitiAuditWriter()
        w._graph_manager = None  # Force Graphiti unavailable
        return w

    def test_log_ingestion_audit_returns_false_when_unavailable(self, writer):
        """When Graphiti is unavailable, audit returns False (not raise)."""
        result = writer.log_ingestion_audit(
            workspace_id="ws1",
            doc_id="doc1",
            source_type="news_ingest",
            source_url="http://example.com",
            raw_data_ref="minio://bucket/key",
            query="test query",
            text_length=100,
        )
        assert result is False

    def test_log_extraction_audit_returns_false_when_unavailable(self, writer):
        result = writer.log_extraction_audit(
            workspace_id="ws1",
            ontology_id="ont1",
            session_id="sess1",
            template_id="general/base_graph",
            extraction_method="he_feed_to_kb",
            entity_count=10,
            relation_count=5,
        )
        assert result is False

    def test_log_reasoning_audit_returns_false_when_unavailable(self, writer):
        result = writer.log_reasoning_audit(
            workspace_id="ws1",
            reasoning_engine="test_engine",
            input_facts=["fact1"],
            reasoning_path=["step1", "step2"],
            output_conclusion="test conclusion",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_log_ingestion_audit_async_returns_false_when_unavailable(self, writer):
        result = await writer.log_ingestion_audit_async(
            workspace_id="ws1",
            doc_id="doc1",
            source_type="news_ingest",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_log_extraction_audit_async_returns_false_when_unavailable(self, writer):
        result = await writer.log_extraction_audit_async(
            workspace_id="ws1",
            ontology_id="ont1",
            session_id="sess1",
        )
        assert result is False

    def test_log_ingestion_audit_with_mock_graph_manager(self):
        """When GraphManager is available, log_ingestion_audit should call save_audit_episode."""
        from odap.infra.security.graphiti_audit_writer import GraphitiAuditWriter
        mock_gm = MagicMock()
        mock_gm.save_audit_episode = AsyncMock(return_value=True)

        w = GraphitiAuditWriter()
        w._graph_manager = mock_gm

        result = w.log_ingestion_audit(
            workspace_id="ws1",
            doc_id="doc1",
            source_type="news_ingest",
        )
        assert result is True
        mock_gm.save_audit_episode.assert_called_once()
        call_kwargs = mock_gm.save_audit_episode.call_args[1]
        assert call_kwargs["audit_data"]["audit_type"] == "#1_ingestion"
        assert call_kwargs["audit_data"]["doc_id"] == "doc1"

    def test_log_extraction_audit_with_mock_graph_manager(self):
        from odap.infra.security.graphiti_audit_writer import GraphitiAuditWriter
        mock_gm = MagicMock()
        mock_gm.save_audit_episode = AsyncMock(return_value=True)

        w = GraphitiAuditWriter()
        w._graph_manager = mock_gm

        result = w.log_extraction_audit(
            workspace_id="ws1",
            ontology_id="ont1",
            session_id="sess1",
            template_id="test_template",
            entity_count=5,
        )
        assert result is True
        call_kwargs = mock_gm.save_audit_episode.call_args[1]
        assert call_kwargs["audit_data"]["audit_type"] == "#2_extraction"
        assert call_kwargs["audit_data"]["entity_count"] == 5


# ===========================================================================
# Iter 3.2: audit_helper.confirm_audit / query_audit
# ===========================================================================

class TestAuditHelperConfirmQuery:
    """Test the new confirm_audit and query_audit functions."""

    @patch("odap.infra.security.audit_helper.audit")
    def test_confirm_audit_calls_audit_with_correct_params(self, mock_audit):
        from odap.infra.security.audit_helper import confirm_audit
        confirm_audit(
            operator="user1",
            ontology_id="ont1",
            session_id="sess1",
            decision="confirmed",
            changes={"entity_count": {"before": 5, "after": 7}},
        )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["action"] == "extraction_confirmed"
        assert call_kwargs["user"] == "user1"
        assert call_kwargs["result_status"] == "success"
        assert call_kwargs["service"] == "hitl_confirm"

    @patch("odap.infra.security.audit_helper.audit")
    def test_confirm_audit_rejected_is_denied(self, mock_audit):
        from odap.infra.security.audit_helper import confirm_audit
        confirm_audit(
            operator="user1",
            ontology_id="ont1",
            session_id="sess1",
            decision="rejected",
        )
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["result_status"] == "denied"

    @patch("odap.infra.security.audit_helper.audit")
    def test_query_audit_calls_audit_with_correct_params(self, mock_audit):
        from odap.infra.security.audit_helper import query_audit
        query_audit(
            operator="agent1",
            query_params={"query": "test", "retrieval_type": "semantic"},
            result_summary={"count": 5, "entity_ids": ["e1", "e2"]},
            duration_ms=42,
        )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["action"] == "query_execute"
        assert call_kwargs["user"] == "agent1"
        assert call_kwargs["service"] == "retrieval_service"
        assert call_kwargs["duration_ms"] == 42

    @patch("odap.infra.security.audit_helper.audit")
    def test_query_audit_result_message_includes_count(self, mock_audit):
        from odap.infra.security.audit_helper import query_audit
        query_audit(
            operator="user1",
            query_params={"retrieval_type": "graph"},
            result_summary={"count": 10},
        )
        call_kwargs = mock_audit.call_args[1]
        assert "10 results" in call_kwargs["result_message"]


# ===========================================================================
# Iter 3.2: NewsIngester #1 ingestion audit instrumentation
# ===========================================================================

class TestNewsIngesterAuditInstrumentation:
    """Verify NewsIngester calls audit writer after ingestion."""

    @pytest.fixture
    def ingester(self):
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        return NewsIngester()

    @pytest.mark.asyncio
    async def test_audit_called_after_ingestion(self, ingester):
        """_audit_ingestion should be called after producing docs."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_audit_ingestion") as mock_audit:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            await ingester.ingest("query", workspace_id="ws1")
            mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_break_ingestion(self, ingester):
        """Audit failure should be caught and logged, not propagated."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_audit_ingestion", side_effect=Exception("audit crash")):
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            # Should not raise
            docs = await ingester.ingest("query", workspace_id="ws1")
            assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_audit_ingestion_calls_writer(self, ingester):
        """_audit_ingestion should call GraphitiAuditWriter.log_ingestion_audit."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"title": "t", "url": "u", "content": "c"}]
            with patch(
                "odap.infra.security.graphiti_audit_writer.GraphitiAuditWriter.log_ingestion_audit"
            ) as mock_log:
                mock_log.return_value = False  # Graphiti unavailable
                await ingester.ingest("query", workspace_id="ws1")
                mock_log.assert_called_once()
                call_kwargs = mock_log.call_args[1]
                assert call_kwargs["workspace_id"] == "ws1"
                assert call_kwargs["source_type"] is not None


# ===========================================================================
# Iter 3.2: ExtractService #2 extraction audit instrumentation
# ===========================================================================

class TestExtractServiceAuditInstrumentation:
    """Verify ExtractService calls audit writer after extraction."""

    @pytest.mark.asyncio
    async def test_audit_extraction_method_exists(self):
        """ExtractService should have _audit_extraction method."""
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        assert hasattr(ExtractService, "_audit_extraction")

    @pytest.mark.asyncio
    async def test_audit_extraction_does_not_raise_on_failure(self):
        """_audit_extraction should catch exceptions and not propagate."""
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        svc = ExtractService()
        # Should not raise even when GraphitiAuditWriter fails
        await svc._audit_extraction(
            workspace_id="ws1",
            ontology_id="ont1",
            session_id="sess1",
        )  # No exception = pass


# ===========================================================================
# Integration: full ingestion flow with audit + raw_data_ref
# ===========================================================================

class TestIngestionFlowWithAuditAndPersistence:
    """End-to-end: ingestion → raw_data_ref → audit."""

    @pytest.fixture
    def ingester(self):
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        return NewsIngester()

    @pytest.mark.asyncio
    async def test_full_flow_produces_doc_with_ref_and_audit(self, ingester):
        """Ingestion should produce a doc with raw_data_ref AND trigger audit."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_audit_ingestion") as mock_audit:
            mock_search.return_value = [
                {"title": "News 1", "url": "http://example.com/1", "content": "Content 1"},
                {"title": "News 2", "url": "http://example.com/2", "content": "Content 2"},
            ]
            docs = await ingester.ingest("test query", workspace_id="ws1")

            # Doc has raw_data_ref
            assert docs[0].raw_data_ref is not None
            assert docs[0].raw_data_ref.startswith("file://")

            # Audit was called
            mock_audit.assert_called_once()

            # Doc is pending state
            assert docs[0].transformation_status == "pending"

    @pytest.mark.asyncio
    async def test_raw_data_ref_downloadable(self, ingester, tmp_path):
        """The raw_data_ref should point to downloadable data."""
        with patch.object(ingester, "_search", new_callable=AsyncMock) as mock_search, \
             patch.object(ingester, "_audit_ingestion"):
            mock_search.return_value = [
                {"title": "Test", "url": "http://example.com", "content": "Downloadable content"},
            ]
            docs = await ingester.ingest("query", workspace_id="ws1")

            # Download the raw data
            storage = get_raw_data_storage()
            download = storage.download_raw(docs[0].raw_data_ref)
            assert download["status"] == "success"
            assert "Downloadable content" in download["text"]
