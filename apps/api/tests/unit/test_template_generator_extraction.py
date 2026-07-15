"""TemplateEngine.generate_from_ontology() extraction tests.

Tests the ontology-based template generation that was absorbed from
the deleted OntologyTemplateGenerator (T073).

Methods select_preset, recommend_templates, _infer_domain, and
generate_with_web_search from the old TemplateGenerator are no longer
tested here — their functionality is replaced by TemplateEngine.assess()
and TemplateEngine.generate_custom(), which are tested in
test_template_engine.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
from odap.biz.data.hyper_extract.storage import Storage


@pytest.fixture
def engine(tmp_path):
    storage = Storage(db_path=str(tmp_path / "test_he_templates.db"))
    return TemplateEngine(HEAdapter(), storage)


_DEFAULT_OBJECT_TYPES = [
    {
        "name": "Company",
        "properties": [
            {"name": "name", "property_type": "STRING"},
            {"name": "revenue", "property_type": "FLOAT"},
        ],
    },
    {
        "name": "Person",
        "properties": [
            {"name": "full_name", "property_type": "STRING"},
        ],
    },
]

_DEFAULT_LINK_TYPES = [
    {
        "name": "employs",
        "source_type": "Company",
        "target_type": "Person",
        "link_type": "ASSOCIATION",
    },
]


def _make_ontology_result(object_types=_DEFAULT_OBJECT_TYPES, link_types=_DEFAULT_LINK_TYPES):
    return {
        "name": "test-ontology",
        "object_types": object_types,
        "link_types": link_types,
    }


def _mock_ontology_service(object_types=None, link_types=None, action_types=None):
    svc = MagicMock()
    svc.get_ontology.return_value = _make_ontology_result(
        object_types=object_types or _DEFAULT_OBJECT_TYPES,
        link_types=link_types or _DEFAULT_LINK_TYPES,
    )
    svc.list_object_types.return_value = {
        "object_types": object_types or _DEFAULT_OBJECT_TYPES,
    }
    svc.list_link_types.return_value = {
        "link_types": link_types or _DEFAULT_LINK_TYPES,
    }
    svc.list_action_types.return_value = {
        "action_types": action_types or [],
    }
    return svc


class TestGenerateFromOntology:

    def test_generate_graph_template_success(self, engine):
        """Without action types, template type is 'graph'."""
        svc = _mock_ontology_service()
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")

        assert result["type"] == "graph"
        assert result["language"] == "zh"
        assert "entities" in result["output"]
        assert "relations" in result["output"]
        assert "events" not in result["output"]

    def test_generate_temporal_graph_with_actions(self, engine):
        """With action types, template type is 'temporal_graph' with events."""
        actions = [{"name": "hire", "target_object_type": "Person", "parameters": []}]
        svc = _mock_ontology_service(action_types=actions)
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")

        assert result["type"] == "temporal_graph"
        assert "events" in result["output"]

    def test_generate_empty_ontology_id(self, engine):
        """Empty ontology_id returns error dict."""
        result = engine.generate_from_ontology("")
        assert result.get("status") == "error"

    def test_generate_service_error(self, engine):
        """When OntologyService returns error, generate propagates it."""
        svc = MagicMock()
        svc.get_ontology.return_value = {"status": "error", "message": "not found"}
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")
        assert result.get("status") == "error"

    def test_generate_entity_fields_include_properties(self, engine):
        """Entity fields should include properties from object types."""
        svc = _mock_ontology_service()
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")

        entity_fields = result["output"]["entities"]["fields"]
        field_names = [f["name"] for f in entity_fields]
        assert "name" in field_names
        assert "type" in field_names
        assert "revenue" in field_names
        assert "full_name" in field_names

    def test_generate_relation_fields_include_core(self, engine):
        """Relation fields should include source, target, type."""
        svc = _mock_ontology_service()
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")

        relation_fields = result["output"]["relations"]["fields"]
        field_names = [f["name"] for f in relation_fields]
        assert "source" in field_names
        assert "target" in field_names
        assert "type" in field_names

    def test_generate_property_type_mapping(self, engine):
        """Property types should be mapped from ODAP to HE format."""
        svc = _mock_ontology_service()
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=svc,
        ):
            result = engine.generate_from_ontology("ont-1")

        entity_fields = result["output"]["entities"]["fields"]
        revenue_field = next(f for f in entity_fields if f["name"] == "revenue")
        assert revenue_field["type"] == "float"
