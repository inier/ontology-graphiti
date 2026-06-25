"""ExtractionService.extract_from_nl TDD tests for refactored HEAdapter pipeline.

Covers 5 scenarios for the REFACTORED extract_from_nl that uses
HEAdapter + OntologyMapper + TemplateGenerator with fallback:

1. test_extract_from_nl_success          — full HEAdapter pipeline
2. test_extract_from_nl_empty_text       — EC-001 empty input guard
3. test_extract_from_nl_template_fallback — 3-level template fallback
4. test_extract_from_nl_he_unavailable   — EC-008 fallback to SchemaLevelExtractor
5. test_extract_from_nl_llm_timeout      — EC-007 TimeoutError handling

Rules (AGENTS.md):
- Mock HEAdapter, OntologyMapper, TemplateGenerator, SchemaLevelExtractor, OntologyService
- Use from unittest.mock import patch, MagicMock, AsyncMock
- Class-based organization
- Import ExtractionService inside fixtures to avoid import errors
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


def _make_ka_result():
    return {
        "nodes": [
            {
                "id": "n1",
                "name": "Customer",
                "type": "entity",
                "description": "A customer entity",
                "attributes": {"email": "x@y.com", "age": 30},
            },
            {
                "id": "n2",
                "name": "Order",
                "type": "entity",
                "description": "An order entity",
                "attributes": {"total": 99.9},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "name": "places",
                "type": "ASSOCIATION",
                "source": "n1",
                "target": "n2",
                "description": "Customer places Order",
            }
        ],
    }


def _make_mapped_schema():
    return {
        "object_types": [
            {
                "name": "Customer",
                "display_name": "Customer",
                "description": "A customer entity",
                "properties": [
                    {"name": "email", "property_type": "STRING"},
                    {"name": "age", "property_type": "NUMBER"},
                ],
            },
            {
                "name": "Order",
                "display_name": "Order",
                "description": "An order entity",
                "properties": [{"name": "total", "property_type": "NUMBER"}],
            },
        ],
        "link_types": [
            {
                "name": "places",
                "source_type": "n1",
                "target_type": "n2",
                "cardinality": "ONE_TO_MANY",
                "link_type": "ASSOCIATION",
                "description": "Customer places Order",
            }
        ],
        "action_types": [],
        "rule_types": [],
        "process_types": [],
        "function_types": [],
        "indicator_types": [],
    }


def _make_mapped_instances():
    return {
        "entities": [
            {
                "name": "Customer",
                "type": "entity",
                "attributes": {"email": "x@y.com", "age": 30},
                "id": "n1",
            },
            {
                "name": "Order",
                "type": "entity",
                "attributes": {"total": 99.9},
                "id": "n2",
            },
        ],
        "relations": [
            {
                "name": "places",
                "source_id": "n1",
                "target_id": "n2",
                "attributes": {},
                "id": "e1",
            }
        ],
    }


def _make_schema_extractor_result():
    return {
        "status": "ok",
        "object_types": [
            {
                "name": "fallback_entity",
                "display_name": "FallbackEntity",
                "description": "From SchemaLevelExtractor",
                "properties": [],
            }
        ],
        "link_types": [],
        "action_types": [],
        "rule_types": [],
        "process_types": [],
        "function_types": [],
        "indicator_types": [],
        "summary": {"object_types": 1},
    }


_HE_ADAPTER_PATH = "odap.biz.core.ontology.extraction.impl.he_adapter.HEAdapter"
_MAPPER_PATH = "odap.biz.core.ontology.extraction.impl.ontology_mapper.OntologyMapper"
_TEMPLATE_GEN_PATH = "odap.biz.core.ontology.extraction.impl.template_generator.TemplateGenerator"
_SCHEMA_EXTRACTOR_PATH = "odap.biz.core.ontology.extraction.services.schema_extractor.SchemaLevelExtractor"


class TestExtractionServiceNL:

    async def test_extract_from_nl_success(self, service, ontology_id):
        ka_result = _make_ka_result()
        mapped_schema = _make_mapped_schema()
        mapped_instances = _make_mapped_instances()

        mock_he = MagicMock()
        mock_he.available = True
        mock_he.extract_from_text = MagicMock(return_value=ka_result)

        mock_mapper = MagicMock()
        mock_mapper.map_to_schema = MagicMock(return_value=mapped_schema)
        mock_mapper.map_to_instances = MagicMock(return_value=mapped_instances)

        mock_template_gen = MagicMock()
        mock_template_gen.generate_from_ontology = MagicMock(
            return_value={"name": "ontology_test", "auto_type": "graph", "method": "graph_rag", "language": "zh"}
        )

        with patch(_HE_ADAPTER_PATH, return_value=mock_he), \
             patch(_MAPPER_PATH, return_value=mock_mapper), \
             patch(_TEMPLATE_GEN_PATH, return_value=mock_template_gen):
            result = await service.extract_from_nl(
                ontology_id=ontology_id,
                text="Customers place orders in an e-commerce system",
            )

        assert result["status"] == "ok"
        assert "session_id" in result
        assert result["session_id"]

        session = service.ontology_service.get_extraction_session(result["session_id"])
        assert session is not None
        assert session["extraction_type"] == "natural_language"
        assert session["ontology_id"] == ontology_id

        assert "result" in result
        schema = result["result"]
        assert len(schema["object_types"]) == 2
        assert len(schema["link_types"]) == 1

        assert "conflicts" in result
        assert isinstance(result["conflicts"], list)

        mock_he.extract_from_text.assert_called_once()
        mock_mapper.map_to_schema.assert_called_once_with(ka_result)
        mock_mapper.map_to_instances.assert_called_once_with(ka_result)

    async def test_extract_from_nl_empty_text(self, service, ontology_id):
        result = await service.extract_from_nl(
            ontology_id=ontology_id,
            text="",
        )

        assert result["status"] == "error"
        assert "Text cannot be empty" in result["message"]

    async def test_extract_from_nl_template_fallback(self, service, ontology_id):
        ka_result = _make_ka_result()
        mapped_schema = _make_mapped_schema()
        mapped_instances = _make_mapped_instances()

        mock_he = MagicMock()
        mock_he.available = True
        mock_he.extract_from_text = MagicMock(return_value=ka_result)

        mock_mapper = MagicMock()
        mock_mapper.map_to_schema = MagicMock(return_value=mapped_schema)
        mock_mapper.map_to_instances = MagicMock(return_value=mapped_instances)

        mock_template_gen = MagicMock()
        mock_template_gen.generate_from_ontology = MagicMock(return_value=None)
        preset_template = {
            "name": "general/base_graph",
            "auto_type": "graph",
            "method": "graph_rag",
            "language": "zh",
            "source": "preset",
        }
        mock_template_gen.select_preset = MagicMock(return_value=preset_template)
        mock_template_gen._infer_domain = MagicMock(return_value="general")

        with patch(_HE_ADAPTER_PATH, return_value=mock_he), \
             patch(_MAPPER_PATH, return_value=mock_mapper), \
             patch(_TEMPLATE_GEN_PATH, return_value=mock_template_gen):
            result = await service.extract_from_nl(
                ontology_id=ontology_id,
                text="Some domain text",
            )

        assert result["status"] == "ok"

        mock_template_gen.generate_from_ontology.assert_called_once_with(ontology_id)
        mock_template_gen.select_preset.assert_called_once()

        mock_he.extract_from_text.assert_called_once()
        call_args = mock_he.extract_from_text.call_args
        template_config = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("template_config", call_args[0][1])
        assert template_config["name"] == "general/base_graph"
        assert template_config["source"] == "preset"

    async def test_extract_from_nl_he_unavailable(self, service, ontology_id):
        fallback_result = _make_schema_extractor_result()

        mock_he = MagicMock()
        mock_he.available = False

        mock_mapper = MagicMock()
        mock_template_gen = MagicMock()

        with patch(_HE_ADAPTER_PATH, return_value=mock_he), \
             patch(_MAPPER_PATH, return_value=mock_mapper), \
             patch(_TEMPLATE_GEN_PATH, return_value=mock_template_gen), \
             patch(_SCHEMA_EXTRACTOR_PATH) as MockSchemaExtractor:
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.extract_from_text = AsyncMock(return_value=fallback_result)
            MockSchemaExtractor.return_value = mock_extractor_instance

            result = await service.extract_from_nl(
                ontology_id=ontology_id,
                text="A domain description for fallback extraction",
            )

        assert result["status"] == "ok"
        assert "session_id" in result

        assert "result" in result
        assert len(result["result"]["object_types"]) == 1
        assert result["result"]["object_types"][0]["name"] == "fallback_entity"

        mock_mapper.map_to_schema.assert_not_called()
        mock_mapper.map_to_instances.assert_not_called()
        mock_he.extract_from_text.assert_not_called()

        mock_extractor_instance.extract_from_text.assert_called_once()

    async def test_extract_from_nl_llm_timeout(self, service, ontology_id):
        mock_he = MagicMock()
        mock_he.available = True
        mock_he.extract_from_text = MagicMock(side_effect=TimeoutError("LLM call timed out"))

        mock_mapper = MagicMock()
        mock_template_gen = MagicMock()
        mock_template_gen.generate_from_ontology = MagicMock(
            return_value={"name": "test_template", "auto_type": "graph", "method": "graph_rag", "language": "zh"}
        )

        with patch(_HE_ADAPTER_PATH, return_value=mock_he), \
             patch(_MAPPER_PATH, return_value=mock_mapper), \
             patch(_TEMPLATE_GEN_PATH, return_value=mock_template_gen):
            result = await service.extract_from_nl(
                ontology_id=ontology_id,
                text="A domain description that triggers timeout",
            )

        assert result["status"] == "error"
        assert "timed out" in result["message"].lower()

        mock_mapper.map_to_schema.assert_not_called()
        mock_mapper.map_to_instances.assert_not_called()
