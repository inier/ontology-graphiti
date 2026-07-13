"""ExtractionService delegation tests — verifies the old ExtractionService
properly delegates HE-based extraction to the new ExtractService.

Since the old ExtractionService was rewritten as a thin delegation layer
(T068), these tests verify:
1. extract_from_nl delegates to he_service.extract_from_nl
2. extract_from_document delegates to he_service.extract_from_document
3. extract_from_knowledge_base delegates to he_service.extract_from_knowledge_base
4. confirm_extraction delegates to he_service.confirm_extraction
5. get_session tries new storage first, falls back to OntologyService
6. extract_from_database still works (no HE, uses DatabaseSchemaExtractor)
7. Empty text returns error before delegation
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def service(tmp_path):
    from odap.biz.core.ontology.extraction.services.extraction_service import (
        ExtractionService,
    )
    db_path = str(tmp_path / "test_extraction_nl.db")
    return ExtractionService(db_path=db_path)


@pytest.fixture
def ontology_service(tmp_path):
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )
    db_path = str(tmp_path / "test_extraction_nl.db")
    return OntologyService(db_path=db_path)


@pytest.fixture
def ontology_id(ontology_service):
    result = ontology_service.create_ontology(
        name="test-ontology-nl",
        description="Test ontology for NL extraction",
    )
    return result["ontology_id"]


class TestExtractionServiceDelegation:
    """Verify old ExtractionService delegates to new ExtractService."""

    async def test_extract_from_nl_delegates(self, service, ontology_id):
        """extract_from_nl should delegate to he_service.extract_from_nl."""
        mock_he = AsyncMock()
        mock_he.extract_from_nl = AsyncMock(return_value={
            "status": "ok",
            "session_id": "test-session",
            "result": {"object_types": [], "link_types": []},
            "template_used": "general/base_graph",
        })
        service._he_extract_service = mock_he

        result = await service.extract_from_nl(
            ontology_id=ontology_id,
            text="Customers place orders",
        )

        assert result["status"] == "ok"
        assert result["session_id"] == "test-session"
        mock_he.extract_from_nl.assert_called_once_with(
            text="Customers place orders",
            ontology_id=ontology_id,
            template_id=None,
            method=None,
        )

    async def test_extract_from_nl_empty_text(self, service, ontology_id):
        """Empty text should return error from delegated ExtractService."""
        result = await service.extract_from_nl(
            ontology_id=ontology_id,
            text="",
        )
        assert result["status"] == "error"
        assert "不能为空" in result["message"]

    async def test_extract_from_document_delegates(self, service, ontology_id):
        """extract_from_document should delegate to he_service."""
        mock_he = AsyncMock()
        mock_he.extract_from_document = AsyncMock(return_value={
            "status": "ok",
            "session_id": "doc-session",
            "result": {},
        })
        service._he_extract_service = mock_he

        result = await service.extract_from_document(
            ontology_id=ontology_id,
            file_path="/tmp/test.pdf",
        )

        assert result["status"] == "ok"
        mock_he.extract_from_document.assert_called_once_with(
            file_path="/tmp/test.pdf",
            ontology_id=ontology_id,
            template_id=None,
            method=None,
        )

    async def test_extract_from_kb_delegates(self, service, ontology_id):
        """extract_from_knowledge_base should delegate to he_service."""
        mock_he = AsyncMock()
        mock_he.extract_from_knowledge_base = AsyncMock(return_value={
            "status": "ok",
            "session_id": "kb-session",
            "result": {},
        })
        service._he_extract_service = mock_he

        result = await service.extract_from_knowledge_base(
            ontology_id=ontology_id,
            kb_id="test-kb",
        )

        assert result["status"] == "ok"
        mock_he.extract_from_knowledge_base.assert_called_once()

    async def test_confirm_extraction_delegates(self, service):
        """confirm_extraction should delegate to he_service."""
        mock_he = AsyncMock()
        mock_he.confirm_extraction = AsyncMock(return_value={
            "status": "ok",
            "imported": {"object_types": 2},
        })
        service._he_extract_service = mock_he

        result = await service.confirm_extraction(
            session_id="test-session",
            merge_strategy="skip",
        )

        assert result["status"] == "ok"
        mock_he.confirm_extraction.assert_called_once_with(
            session_id="test-session",
            selected=None,
            data=None,
            merge_strategy="skip",
        )

    def test_get_session_falls_back_to_ontology_service(self, service):
        """get_session should try new ExtractService first, then OntologyService."""
        # Mock he_service.get_session to return not found
        mock_he = MagicMock()
        mock_he.get_session = MagicMock(return_value={
            "status": "error",
            "message": "Session not found",
        })
        service._he_extract_service = mock_he

        # Mock ontology_service.get_extraction_session to return a session
        service.ontology_service = MagicMock()
        service.ontology_service.get_extraction_session = MagicMock(return_value={
            "status": "ok",
            "session_id": "db-session",
            "extraction_type": "database",
        })

        result = service.get_session("db-session")
        assert result["status"] == "ok"
        assert result["extraction_type"] == "database"

    def test_get_session_returns_new_when_available(self, service):
        """get_session should return new ExtractService session when available."""
        mock_he = MagicMock()
        mock_he.get_session = MagicMock(return_value={
            "status": "ok",
            "session_id": "he-session",
            "result_data": {"validation_report": {}},
        })
        service._he_extract_service = mock_he

        result = service.get_session("he-session")
        assert result["status"] == "ok"
        assert result["session_id"] == "he-session"

    def test_he_service_lazy_init(self, service):
        """he_service property should lazy-init the new ExtractService."""
        assert service._he_extract_service is None
        he = service.he_service
        assert he is not None
        assert service._he_extract_service is he
