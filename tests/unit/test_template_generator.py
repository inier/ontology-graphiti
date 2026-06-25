"""OntologyTemplateGenerator unit tests.

Covers:
- generate graph template (no action types)
- generate temporal_graph template (with action types)
- generate with empty ontology_id returns error
- generate handles OntologyService error

Rules (AGENTS.md):
- Mock external services (OntologyService) but NOT storage layer
- Service layer tests verify: success returns flat dict, error returns {"status": "error", ...}
"""

import pytest
from unittest.mock import patch, MagicMock

from odap.biz.data.hyper_extract.services.template_generator import (
    OntologyTemplateGenerator,
)


def _mock_ontology_service():
    """Factory for a mock OntologyService with predefined type data."""
    service = MagicMock()
    service.get_ontology.return_value = {
        "name": "test-ontology",
        "description": "Test",
    }
    service.list_object_types.return_value = {
        "object_types": [
            {
                "name": "Organization",
                "type_id": "org-1",
                "properties": [
                    {"name": "name", "property_type": "STRING"},
                    {"name": "employee_count", "property_type": "INTEGER"},
                ],
            },
        ],
        "count": 1,
    }
    service.list_link_types.return_value = {
        "link_types": [
            {
                "name": "owns",
                "source_type": "Organization",
                "target_type": "Satellite",
                "properties": [],
            },
        ],
        "count": 1,
    }
    service.list_action_types.return_value = {
        "action_types": [],
        "count": 0,
    }
    return service


class TestOntologyTemplateGenerator:
    """Tests for OntologyTemplateGenerator with mocked OntologyService."""

    def test_generate_graph_template(self):
        """Without action types, template type is 'graph' with entities and relations."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            gen = OntologyTemplateGenerator()
            result = gen.generate("ont-1")
            assert result["type"] == "graph"
            assert "entities" in result["output"]
            assert "relations" in result["output"]
            assert result["language"] == "zh"

    def test_generate_temporal_graph_with_actions(self):
        """With action types, template type is 'temporal_graph' with events section."""
        svc = _mock_ontology_service()
        svc.list_action_types.return_value = {
            "action_types": [
                {
                    "name": "launch",
                    "target_object_type": "Satellite",
                    "parameters": [],
                },
            ],
            "count": 1,
        }
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            gen = OntologyTemplateGenerator()
            result = gen.generate("ont-1")
            assert result["type"] == "temporal_graph"
            assert "events" in result["output"]

    def test_generate_empty_ontology_id(self):
        """Empty ontology_id returns error dict."""
        gen = OntologyTemplateGenerator()
        result = gen.generate("")
        assert result.get("status") == "error"

    def test_generate_handles_service_error(self):
        """When OntologyService returns error, generate propagates it."""
        svc = _mock_ontology_service()
        svc.list_object_types.return_value = {
            "status": "error",
            "message": "not found",
        }
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            gen = OntologyTemplateGenerator()
            result = gen.generate("ont-1")
            assert result.get("status") == "error"
