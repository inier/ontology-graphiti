"""Integration tests: confirm_extraction dual-channel write.

Requires: Neo4j reachable (Channel B needs Graphiti).
Uses pre-created sessions with result_data to avoid needing OPENAI_API_KEY
for the extraction step — only the confirm/write step needs Neo4j.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.integration

# --- Neo4j reachability check (follows test_ontology_graphiti.py pattern) ---
NEO4J_AVAILABLE = False
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    pass

_neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_neo4j_user = os.getenv("NEO4J_USER", "neo4j")
_neo4j_password = os.getenv("NEO4J_PASSWORD", "password")


def _neo4j_reachable() -> bool:
    if not NEO4J_AVAILABLE:
        return False
    try:
        driver = GraphDatabase.driver(_neo4j_uri, auth=(_neo4j_user, _neo4j_password))
        with driver.session() as s:
            s.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


_skip_if_no_neo4j = pytest.mark.skipif(
    not _neo4j_reachable(),
    reason="Neo4j not available for dual-channel write integration test",
)


def _make_result_data():
    """Build realistic result_data with source_template provenance tags."""
    return {
        "object_types": [
            {
                "name": "Person",
                "type": "object",
                "description": "人物实体",
                "source_template": "custom_test_template",
            },
            {
                "name": "Company",
                "type": "object",
                "description": "公司实体",
                "source_template": "custom_test_template",
            },
        ],
        "link_types": [
            {
                "name": "CEO_of",
                "source": "Person",
                "target": "Company",
                "source_template": "custom_test_template",
            },
        ],
        "action_types": [],
        "rule_types": [],
        "process_types": [],
    }


@_skip_if_no_neo4j
class TestDualChannelWrite:
    """confirm_extraction dual-channel write integration tests."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService
        from odap.biz.data.hyper_extract.storage import Storage
        from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker

        self.tmp_path = tmp_path
        self.storage = Storage(db_path=str(tmp_path / "extraction.db"))
        self.provenance_tracker = ProvenanceTracker(
            db_path=str(tmp_path / "provenance.db")
        )
        self.service = ExtractService(
            storage=self.storage,
            provenance_tracker=self.provenance_tracker,
        )
        self.ontology_id = f"test-dual-{uuid.uuid4().hex[:8]}"

    def _create_session_with_result(self):
        """Create a session pre-populated with result_data (no LLM needed)."""
        session = self.storage.create_session(
            ontology_id=self.ontology_id,
            extraction_type="natural_language",
            input_data={"text": "test text for dual channel write"},
        )
        session_id = session["session_id"]
        self.storage.update_session(session_id, {"result_data": _make_result_data()})
        return session_id

    async def test_confirm_extraction_returns_channel_statuses(self):
        """confirm_extraction() must return channel_a_status and channel_b_status."""
        session_id = self._create_session_with_result()

        result = await self.service.confirm_extraction(session_id)

        assert result["status"] == "ok", f"confirm failed: {result.get('message', '')}"
        assert "channel_a_status" in result, "Missing channel_a_status"
        assert "channel_b_status" in result, "Missing channel_b_status"

        imported = result["imported"]
        assert imported["object_types"] == 2, "Expected 2 object_types imported"
        assert imported["link_types"] == 1, "Expected 1 link_type imported"

    async def test_confirm_extraction_updates_session_to_completed(self):
        """After confirm, session status must be 'completed'."""
        session_id = self._create_session_with_result()

        await self.service.confirm_extraction(session_id)

        updated = self.storage.get_session(session_id)
        assert updated is not None, "Session should exist after confirm"
        assert updated["status"] == "completed", (
            f"Session status should be 'completed', got '{updated['status']}'"
        )

    async def test_confirm_extraction_records_provenance_with_source_template(self):
        """ProvenanceTracker must record source_template for each imported item."""
        session_id = self._create_session_with_result()

        await self.service.confirm_extraction(session_id)

        # entity_id format: {ontology_id}_{category}_{item_name}
        person_entity_id = f"{self.ontology_id}_object_Person"
        prov = self.provenance_tracker.get_provenance(person_entity_id)

        assert prov is not None, (
            f"Provenance not recorded for entity: {person_entity_id}"
        )
        assert prov["source_template"] == "custom_test_template", (
            f"source_template mismatch: {prov.get('source_template')}"
        )
        assert prov["extraction_method"] == "hyper_extract"
        assert prov["session_id"] == session_id
