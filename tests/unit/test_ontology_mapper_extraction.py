import pytest
from typing import Dict, Any


@pytest.fixture
def mapper():
    from odap.biz.core.ontology.extraction.impl.ontology_mapper import OntologyMapper
    return OntologyMapper()


def _make_node(**overrides) -> Dict[str, Any]:
    defaults = {
        "id": "node-1",
        "name": "TestNode",
        "type": "entity",
        "description": "A test node",
        "attributes": {},
    }
    defaults.update(overrides)
    return defaults


def _make_edge(**overrides) -> Dict[str, Any]:
    defaults = {
        "id": "edge-1",
        "name": "TestEdge",
        "type": "relation",
        "source": "NodeA",
        "target": "NodeB",
        "description": "A test edge",
        "link_type": "ASSOCIATION",
        "attributes": {},
    }
    defaults.update(overrides)
    return defaults


class TestOntologyMapper:

    def test_map_to_schema_extracts_object_types(self, mapper):
        nodes = [
            _make_node(id="n1", name="Person", type="entity", attributes={"age": 30}),
            _make_node(id="n2", name="Company", type="object", attributes={"revenue": 1000}),
        ]
        result = mapper.map_to_schema({"nodes": nodes, "edges": []})
        assert len(result["object_types"]) == 2
        person = result["object_types"][0]
        assert person["name"] == "Person"
        assert person["display_name"] == "Person"
        assert person["description"] == "A test node"
        assert len(person["properties"]) == 1
        assert person["properties"][0]["name"] == "age"
        assert person["properties"][0]["property_type"] == "NUMBER"
        company = result["object_types"][1]
        assert company["name"] == "Company"
        assert company["properties"][0]["name"] == "revenue"

    def test_map_to_schema_extracts_link_types(self, mapper):
        edges = [
            _make_edge(name="WORKS_FOR", source="Person", target="Company", link_type="COMPOSITION"),
        ]
        result = mapper.map_to_schema({"nodes": [], "edges": edges})
        assert len(result["link_types"]) == 1
        link = result["link_types"][0]
        assert link["name"] == "WORKS_FOR"
        assert link["source_type"] == "Person"
        assert link["target_type"] == "Company"
        assert link["cardinality"] == "ONE_TO_MANY"
        assert link["link_type"] == "COMPOSITION"
        assert link["description"] == "A test edge"

    def test_map_to_schema_empty_input(self, mapper):
        result = mapper.map_to_schema({"nodes": [], "edges": []})
        assert result["object_types"] == []
        assert result["link_types"] == []
        assert result["action_types"] == []
        assert result["rule_types"] == []
        assert result["process_types"] == []
        assert result["function_types"] == []
        assert result["indicator_types"] == []

    def test_map_to_schema_property_type_mapping(self, mapper):
        nodes = [
            _make_node(
                name="Mixed",
                attributes={"count": 42, "ratio": 3.14, "active": True, "label": "hello"},
            ),
        ]
        result = mapper.map_to_schema({"nodes": nodes, "edges": []})
        props = {p["name"]: p["property_type"] for p in result["object_types"][0]["properties"]}
        assert props["count"] == "NUMBER"
        assert props["ratio"] == "NUMBER"
        assert props["active"] == "BOOLEAN"
        assert props["label"] == "STRING"

    def test_map_to_schema_ignores_non_entity_nodes(self, mapper):
        nodes = [
            _make_node(name="Event1", type="event"),
            _make_node(name="Action1", type="action"),
            _make_node(name="Entity1", type="entity"),
        ]
        result = mapper.map_to_schema({"nodes": nodes, "edges": []})
        assert len(result["object_types"]) == 1
        assert result["object_types"][0]["name"] == "Entity1"

    def test_map_to_instances_extracts_entities(self, mapper):
        nodes = [
            _make_node(id="n1", name="Alice", type="person", attributes={"age": 30}),
        ]
        result = mapper.map_to_instances({"nodes": nodes, "edges": []})
        assert len(result["entities"]) == 1
        entity = result["entities"][0]
        assert entity["name"] == "Alice"
        assert entity["type"] == "person"
        assert entity["attributes"] == {"age": 30}
        assert entity["id"] == "n1"

    def test_map_to_instances_extracts_relations(self, mapper):
        edges = [
            _make_edge(id="e1", name="KNOWS", source="n1", target="n2", attributes={"since": 2020}),
        ]
        result = mapper.map_to_instances({"nodes": [], "edges": edges})
        assert len(result["relations"]) == 1
        rel = result["relations"][0]
        assert rel["name"] == "KNOWS"
        assert rel["source_id"] == "n1"
        assert rel["target_id"] == "n2"
        assert rel["attributes"] == {"since": 2020}
        assert rel["id"] == "e1"

    def test_map_to_instances_empty_input(self, mapper):
        result = mapper.map_to_instances({"nodes": [], "edges": []})
        assert result["entities"] == []
        assert result["relations"] == []

    def test_map_to_schema_full_7_type_output(self, mapper):
        result = mapper.map_to_schema({"nodes": [], "edges": []})
        expected_keys = {
            "object_types", "link_types", "action_types",
            "rule_types", "process_types", "function_types", "indicator_types",
        }
        assert set(result.keys()) == expected_keys
        for key in ("action_types", "rule_types", "process_types", "function_types", "indicator_types"):
            assert result[key] == []

    def test_map_to_schema_node_with_no_attributes(self, mapper):
        nodes = [
            _make_node(name="BareEntity", attributes={}),
            _make_node(name="NoAttrKey"),
        ]
        del nodes[1]["attributes"]
        result = mapper.map_to_schema({"nodes": nodes, "edges": []})
        assert len(result["object_types"]) == 2
        assert result["object_types"][0]["properties"] == []
        assert result["object_types"][1]["properties"] == []
