"""Integration tests: real Hyper-Extract + LLM end-to-end extraction.

Requires: Neo4j reachable + OPENAI_API_KEY set + hyperextract installed.
Tests verify REAL HE API calls (no mocks) for parse, feed_text, merge_results,
and the full ExtractService.extract_from_nl() orchestration.
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


_has_openai_key = bool(os.getenv("OPENAI_API_KEY"))

_skip_reason = "Requires Neo4j + OPENAI_API_KEY + hyperextract"
_skip_if_no_env = pytest.mark.skipif(
    not (_neo4j_reachable() and _has_openai_key),
    reason=_skip_reason,
)


@_skip_if_no_env
class TestHERealExtraction:
    """Real HE + LLM end-to-end extraction tests."""

    TEST_TEXT = (
        "张三是ABC公司的CEO。李四是XYZ公司的CTO。"
        "张三和李四共同创立了DEF基金会。"
    )

    @pytest.fixture(autouse=True)
    def _setup_adapter(self):
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        self.adapter = HEAdapter()
        if not self.adapter.is_available():
            pytest.skip("hyperextract not installed")

    def test_parse_returns_entities_and_relations(self):
        """HEAdapter.parse() with real text must return entities/relations."""
        result = self.adapter.parse(self.TEST_TEXT)
        assert result is not None, "parse() returned None — HE API call failed"
        assert "entities" in result
        assert "relations" in result
        # Real text with 3+ named entities should yield at least 1 entity
        assert len(result["entities"]) >= 1, "Expected at least 1 entity from real text"

    def test_feed_text_merges_incremental_results(self):
        """HEAdapter.feed_text() — real incremental extraction via HE API.

        Builds an AutoType instance (same as parse() internal logic), calls
        .parse() for initial text, then feed_text() for additional text.
        Verifies the merged result has at least as many entities as initial.
        """
        llm_client = self.adapter._create_llm_client()
        embedder = self.adapter._create_embedder()
        auto_type = self.adapter._build_auto_graph({}, llm_client, embedder)

        text1 = "张三是ABC公司的CEO。"
        text2 = "李四是XYZ公司的CTO。"

        initial_raw = auto_type.parse(text1)
        initial = self.adapter._normalize_result(initial_raw)
        initial_count = len(initial.get("entities", []))

        # feed_text calls real HE BaseAutoType.feed_text()
        merged = self.adapter.feed_text(auto_type, text2)
        assert merged is not None, "feed_text() returned None"
        merged_count = len(merged.get("entities", []))

        # Merged result should have at least as many entities as initial
        assert merged_count >= initial_count, (
            f"feed_text merged ({merged_count}) < initial ({initial_count})"
        )

    def test_merge_results_deduplicates_by_entity_name(self):
        """HEAdapter.merge_results() — real dedup on overlapping parse results."""
        text1 = "张三是ABC公司的CEO。"
        text2 = "张三是ABC公司的CEO。李四是XYZ公司的CTO。"

        r1 = self.adapter.parse(text1)
        r2 = self.adapter.parse(text2)
        assert r1 is not None and r2 is not None

        merged = self.adapter.merge_results([r1, r2])
        names = [e.get("name", "") for e in merged["entities"]]

        # "张三" appeared in both results — must appear at most once after dedup
        zhang_count = names.count("张三")
        assert zhang_count <= 1, f"Expected '张三' deduped, found {zhang_count} occurrences"

    async def test_extract_from_nl_end_to_end(self):
        """ExtractService.extract_from_nl() — full chain with real HE + LLM."""
        from odap.biz.data.hyper_extract.services.extract_service import ExtractService

        ontology_id = f"test-he-real-{uuid.uuid4().hex[:8]}"
        service = ExtractService()

        result = await service.extract_from_nl(self.TEST_TEXT, ontology_id=ontology_id)

        assert result["status"] == "ok", f"extract_from_nl failed: {result.get('message', '')}"
        assert "session_id" in result

        merged = result["result"]
        assert "object_types" in merged, "Result missing object_types"
        assert "link_types" in merged, "Result missing link_types"

        # template_used must NOT be the schema-level fallback
        template_used = result.get("template_used", "")
        assert template_used != "schema_level_fallback", (
            f"Expected real template, got schema_level_fallback"
        )
        assert template_used is not None, "template_used should not be None"
