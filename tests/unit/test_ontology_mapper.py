"""OntologyMapper unit tests.

Covers:
- map valid entities and relations
- strict mode filters entities with invalid type
- loose mode marks invalid type as "unclassified"
- map empty/None input returns error
- deterministic entity_id generation (sha256 hex[:16])
- four-layer property mapping (basic, statistical, capabilities, constraints)
- strict mode filters relations with invalid relation_type

Rules (AGENTS.md):
- Mock external services (OntologyService) but NOT storage layer
- Service layer tests verify: success returns flat dict, error returns {"status": "error", ...}
"""

import pytest
from unittest.mock import patch, MagicMock

from odap.biz.data.hyper_extract.impl.ontology_mapper import OntologyMapper


def _mock_ontology_service():
    """Factory for a mock OntologyService with predefined type data."""
    service = MagicMock()
    service.list_object_types.return_value = {
        "object_types": [
            {"name": "Organization", "type_id": "org-1"},
            {"name": "Person", "type_id": "person-1"},
            {"name": "Satellite", "type_id": "sat-1"},
        ],
        "count": 3,
    }
    service.list_link_types.return_value = {
        "link_types": [
            {
                "name": "owns",
                "source_type": "Organization",
                "target_type": "Satellite",
            },
            {
                "name": "works_for",
                "source_type": "Person",
                "target_type": "Organization",
            },
        ],
        "count": 2,
    }
    return service


class TestOntologyMapper:
    """Tests for OntologyMapper with mocked OntologyService."""

    def test_map_valid_entities(self):
        """Valid entities are mapped with correct type field."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1")
            ka = {
                "entities": [
                    {
                        "name": "中国",
                        "type": "Organization",
                        "description": "国家",
                        "properties": {},
                    },
                    {
                        "name": "北斗",
                        "type": "Satellite",
                        "description": "导航卫星",
                        "properties": {},
                    },
                ],
                "relations": [
                    {
                        "source": "中国",
                        "target": "北斗",
                        "relation_type": "owns",
                        "properties": {},
                    },
                ],
            }
            result = mapper.map(ka)
            assert "entities" in result
            assert len(result["entities"]) == 2
            assert result["entities"][0]["type"] == "Organization"
            assert result["entities"][1]["type"] == "Satellite"

    def test_map_strict_mode_filters_invalid_type(self):
        """In strict mode, entities with unrecognized type are dropped."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=True)
            ka = {
                "entities": [
                    {
                        "name": "中国",
                        "type": "Organization",
                        "description": "国家",
                        "properties": {},
                    },
                    {
                        "name": "未知",
                        "type": "UnknownType",
                        "description": "未知类型",
                        "properties": {},
                    },
                ],
                "relations": [],
            }
            result = mapper.map(ka)
            assert len(result["entities"]) == 1
            assert result["entities"][0]["name"] == "中国"

    def test_map_loose_mode_marks_unclassified(self):
        """In loose mode, unrecognized entity types are marked as 'unclassified'."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            ka = {
                "entities": [
                    {
                        "name": "未知",
                        "type": "UnknownType",
                        "description": "未知类型",
                        "properties": {},
                    },
                ],
                "relations": [],
            }
            result = mapper.map(ka)
            assert len(result["entities"]) == 1
            assert result["entities"][0]["type"] == "unclassified"

    def test_map_empty_input(self):
        """Mapping None input returns error dict."""
        mapper = OntologyMapper(ontology_id="")
        result = mapper.map(None)
        assert result.get("status") == "error"

    def test_map_deterministic_entity_id(self):
        """Entity IDs are deterministic sha256 hex[:16] based on type:name."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1")
            ka = {
                "entities": [
                    {
                        "name": "中国",
                        "type": "Organization",
                        "description": "国家",
                        "properties": {},
                    },
                ],
                "relations": [],
            }
            result = mapper.map(ka)
            entity_id = result["entities"][0]["entity_id"]
            assert len(entity_id) == 16  # sha256 hex[:16]

    def test_map_properties_four_layers(self):
        """Properties are split into basic, statistical, capabilities, constraints."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1")
            ka = {
                "entities": [
                    {
                        "name": "中国",
                        "type": "Organization",
                        "description": "国家",
                        "properties": {
                            "name": "中国",
                            "total_gdp": 100,
                            "can_trade": True,
                            "max_speed": 300,
                        },
                    },
                ],
                "relations": [],
            }
            result = mapper.map(ka)
            entity = result["entities"][0]
            assert "basic_properties" in entity
            assert "statistical_properties" in entity
            assert "capabilities" in entity
            assert "constraints" in entity

    def test_map_validates_relation_type(self):
        """In strict mode, relations with invalid type are dropped."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=True)
            ka = {
                "entities": [
                    {
                        "name": "中国",
                        "type": "Organization",
                        "description": "",
                        "properties": {},
                    },
                ],
                "relations": [
                    {
                        "source": "中国",
                        "target": "北斗",
                        "relation_type": "invalid_rel",
                        "properties": {},
                    },
                ],
            }
            result = mapper.map(ka)
            assert len(result["relations"]) == 0
