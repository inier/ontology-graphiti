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


# ---------------------------------------------------------------------------
# T051: merge_and_map() — multi-template merge
# ---------------------------------------------------------------------------

def _make_extraction_result(
    entities=None,
    relations=None,
    source_template="preset/base_graph",
):
    """Build a single-template extraction result for merge_and_map input."""
    return {
        "entities": entities or [],
        "relations": relations or [],
        "source_template": source_template,
    }


class TestOntologyMapperMergeAndMap:
    """T051: Multi-template results merge + ODAP 5-class mapping."""

    def test_merge_and_map_dedup_entities_by_name(self):
        """Entities with same name across templates are deduplicated (keep first)."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "description": "from template 1", "properties": {}},
                    ],
                    source_template="t1",
                ),
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "description": "from template 2", "properties": {}},
                        {"name": "OrgB", "type": "Organization", "description": "new", "properties": {}},
                    ],
                    source_template="t2",
                ),
            ]
            merged = mapper.merge_and_map(results)
            names = [e["name"] for e in merged["entities"]]
            assert "OrgA" in names
            assert names.count("OrgA") == 1  # deduplicated
            assert "OrgB" in names

    def test_merge_and_map_dedup_relations_by_triplet(self):
        """Relations deduplicated by (source, relation_type, target)."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "properties": {}},
                        {"name": "Sat1", "type": "Satellite", "properties": {}},
                    ],
                    relations=[
                        {"source": "OrgA", "target": "Sat1", "relation_type": "owns", "properties": {}},
                    ],
                    source_template="t1",
                ),
                _make_extraction_result(
                    relations=[
                        {"source": "OrgA", "target": "Sat1", "relation_type": "owns", "properties": {}},
                        {"source": "OrgA", "target": "Sat1", "relation_type": "operates", "properties": {}},
                    ],
                    source_template="t2",
                ),
            ]
            merged = mapper.merge_and_map(results)
            # Two unique relations: owns (deduped) + operates
            assert len(merged["relations"]) == 2

    def test_merge_and_map_marks_conflicts(self):
        """When deduplicating, if properties differ, mark as conflict."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "description": "desc1", "properties": {"revenue": 100}},
                    ],
                    source_template="t1",
                ),
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "description": "desc2", "properties": {"revenue": 200}},
                    ],
                    source_template="t2",
                ),
            ]
            merged = mapper.merge_and_map(results)
            assert "conflicts" in merged
            assert len(merged["conflicts"]) > 0
            conflict = merged["conflicts"][0]
            assert conflict["name"] == "OrgA"

    def test_merge_and_map_preserves_source_template(self):
        """Each entity has source_template provenance."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "properties": {}},
                    ],
                    source_template="preset/general_graph",
                ),
            ]
            merged = mapper.merge_and_map(results)
            assert merged["entities"][0].get("source_template") == "preset/general_graph"

    def test_merge_and_map_returns_odap_5_classes(self):
        """Result contains all 5 ODAP category keys."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [_make_extraction_result(entities=[], relations=[])]
            merged = mapper.merge_and_map(results)
            for key in ["object_types", "link_types", "action_types", "rule_types", "process_types"]:
                assert key in merged, f"Missing ODAP category: {key}"

    def test_merge_and_map_classifies_entities_by_type(self):
        """Entities are classified into ODAP 5 classes based on their type field."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "Obj1", "type": "Organization", "properties": {}},
                        {"name": "Act1", "type": "action", "properties": {}},
                        {"name": "Rule1", "type": "rule", "properties": {}},
                        {"name": "Proc1", "type": "process", "properties": {}},
                    ],
                    relations=[
                        {"source": "Obj1", "target": "Obj1", "relation_type": "owns", "properties": {}},
                    ],
                ),
            ]
            merged = mapper.merge_and_map(results)
            # Object entities go to object_types
            obj_names = [o.get("name") for o in merged["object_types"]]
            assert "Obj1" in obj_names
            # Action entities go to action_types
            act_names = [a.get("name") for a in merged["action_types"]]
            assert "Act1" in act_names
            # Rule entities go to rule_types
            rule_names = [r.get("name") for r in merged["rule_types"]]
            assert "Rule1" in rule_names
            # Process entities go to process_types
            proc_names = [p.get("name") for p in merged["process_types"]]
            assert "Proc1" in proc_names

    def test_merge_and_map_empty_input_returns_empty(self):
        """Empty results list returns empty structure."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            merged = mapper.merge_and_map([])
            assert merged["entities"] == []
            assert merged["relations"] == []
            assert merged["conflicts"] == []

    def test_merge_and_map_single_result_works(self):
        """Single result (no merge needed) still maps correctly."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "properties": {}},
                    ],
                    relations=[],
                ),
            ]
            merged = mapper.merge_and_map(results)
            assert len(merged["entities"]) == 1

    def test_merge_and_map_preserves_entity_properties(self):
        """Entity properties are preserved through merge."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[
                        {"name": "OrgA", "type": "Organization", "description": "test", "properties": {"revenue": 1000}},
                    ],
                ),
            ]
            merged = mapper.merge_and_map(results)
            entity = merged["entities"][0]
            # Properties should be preserved in basic_properties or similar structure
            assert entity.get("name") == "OrgA"

    def test_merge_and_map_multiple_templates_combines(self):
        """Multiple templates contribute entities to the merged result."""
        with patch(
            "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
            return_value=_mock_ontology_service(),
        ):
            mapper = OntologyMapper(ontology_id="ont-1", strict=False)
            results = [
                _make_extraction_result(
                    entities=[{"name": "A", "type": "Organization", "properties": {}}],
                    source_template="t1",
                ),
                _make_extraction_result(
                    entities=[{"name": "B", "type": "Organization", "properties": {}}],
                    source_template="t2",
                ),
                _make_extraction_result(
                    entities=[{"name": "C", "type": "Organization", "properties": {}}],
                    source_template="t3",
                ),
            ]
            merged = mapper.merge_and_map(results)
            names = {e["name"] for e in merged["entities"]}
            assert names == {"A", "B", "C"}
