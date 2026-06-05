import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEO4J_AVAILABLE = False
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    pass

GRAPHITI_AVAILABLE = False
try:
    from graphiti_core import Graphiti
    GRAPHITI_AVAILABLE = True
except ImportError:
    pass

neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD", "password")


def _neo4j_reachable():
    if not NEO4J_AVAILABLE:
        return False
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


skip_if_no_neo4j = pytest.mark.skipif(
    not _neo4j_reachable(),
    reason="Neo4j not available for integration testing",
)


@skip_if_no_neo4j
class TestOntologyCreateAndStore:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from odap.biz.core.ontology.design.impl.builder import OntologyBuilder
        self.builder = OntologyBuilder()

    def test_create_ontology_document(self):
        doc = self.builder.create_ontology_document(
            name=f"test-ontology-{uuid.uuid4().hex[:8]}",
            description="Integration test ontology",
        )
        assert doc is not None
        assert doc.name.startswith("test-ontology-")
        assert doc.description == "Integration test ontology"

    def test_extract_entities_from_data(self):
        data = {
            "entities": [
                {"entity_type": "Unit", "name": "Alpha-1", "properties": {"side": "blue"}},
                {"entity_type": "Location", "name": "Sector-7", "properties": {"type": "zone"}},
            ],
            "relations": [
                {"source": "Alpha-1", "target": "Sector-7", "relation": "located_at"},
            ],
        }
        result = self.builder.extract_entities(data)
        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.entities[0]["entity_type"] == "Unit"

    def test_build_ontology_from_extracted(self):
        data = {
            "entities": [{"entity_type": "Unit", "name": "Bravo-2"}],
            "relations": [],
        }
        extracted = self.builder.extract_entities(data)
        build = self.builder.build_ontology(f"ingest-{uuid.uuid4().hex[:8]}", extracted)
        assert build.entity_count == 1
        assert build.relation_count == 0
        assert build.status.value == "completed"


@skip_if_no_neo4j
class TestGraphitiTemporalQuery:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from odap.infra.graph.graph_service import GraphManager
        self.graph_manager = GraphManager()

    def test_add_and_query_entity(self):
        entity_data = {
            "name": f"TestEntity-{uuid.uuid4().hex[:8]}",
            "entity_type": "Unit",
            "properties": {"side": "blue", "status": "active"},
        }
        result = self.graph_manager.add_entity(entity_data)
        assert result is not None

    def test_temporal_point_query(self):
        entities = self.graph_manager.search_entities(
            query="Unit", limit=5
        )
        assert isinstance(entities, list)

    def test_entity_with_timestamp(self):
        entity_data = {
            "name": f"TemporalEntity-{uuid.uuid4().hex[:8]}",
            "entity_type": "Location",
            "properties": {"classification": "zone"},
            "valid_at": datetime.now().isoformat(),
        }
        result = self.graph_manager.add_entity(entity_data)
        assert result is not None


@skip_if_no_neo4j
class TestOntologyGraphitiFullChain:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from odap.biz.core.ontology.design.impl.builder import OntologyBuilder
        from odap.infra.graph.graph_service import GraphManager
        self.builder = OntologyBuilder()
        self.graph_manager = GraphManager()

    def test_create_store_query_chain(self):
        doc = self.builder.create_ontology_document(
            name=f"chain-test-{uuid.uuid4().hex[:8]}",
            description="Full chain integration test",
        )
        assert doc is not None

        data = {
            "entities": [
                {"entity_type": "Unit", "name": "ChainUnit-1", "properties": {"side": "red"}},
            ],
            "relations": [],
        }
        extracted = self.builder.extract_entities(data)
        assert len(extracted.entities) == 1

        build = self.builder.build_ontology(f"chain-ingest-{uuid.uuid4().hex[:8]}", extracted)
        assert build.entity_count == 1

        for entity in extracted.entities:
            graph_result = self.graph_manager.add_entity(entity)
            assert graph_result is not None

        query_result = self.graph_manager.search_entities(query="ChainUnit", limit=5)
        assert isinstance(query_result, list)
