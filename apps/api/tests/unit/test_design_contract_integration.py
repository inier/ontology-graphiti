"""
Test the design contract and unified query service integration.

Verifies:
 1. Contract interface methods work end-to-end
 2. View objects are immutable (frozen dataclass)
 3. Unified query service can use the design source
"""
import pytest

from odap.biz.core.ontology.design.contract import (
    EntityTypeView,
    OntologyDesignContract,
    PropertyView,
    RelationTypeView,
    get_design_contract,
)
from odap.infra.query import (
    OntologyDesignSource,
    get_ontology_design_source,
)


def test_design_contract_singleton():
    """get_design_contract() returns the same instance."""
    c1 = get_design_contract()
    c2 = get_design_contract()
    assert c1 is c2
    assert isinstance(c1, OntologyDesignContract)


def test_design_source_singleton():
    """get_ontology_design_source() returns the same instance."""
    s1 = get_ontology_design_source()
    s2 = get_ontology_design_source()
    assert s1 is s2
    assert isinstance(s1, OntologyDesignSource)


def test_view_objects_are_immutable():
    """View objects must be frozen dataclasses."""
    ev = EntityTypeView(
        entity_type_id="et-001",
        name="TestEntity",
        description="A test entity",
        workspace_id="ws-001",
        ontology_id="ont-001",
        properties=(),
        primary_key_fields=(),
        created_at="2026-06-02T00:00:00",
        updated_at="2026-06-02T00:00:00",
        version_id="v-001",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        ev.name = "Changed"


def test_view_object_tuple_types():
    """Properties and primary_key_fields are tuples, not lists."""
    pv = PropertyView(
        name="status",
        data_type="string",
        is_required=True,
    )
    ev = EntityTypeView(
        entity_type_id="et-001",
        name="TestEntity",
        description="",
        workspace_id="ws-001",
        ontology_id="ont-001",
        properties=(pv,),
        primary_key_fields=("id",),
        created_at="",
        updated_at="",
        version_id="v-001",
    )
    assert isinstance(ev.properties, tuple)
    assert isinstance(ev.primary_key_fields, tuple)
    assert ev.properties[0].name == "status"
    assert ev.primary_key_fields[0] == "id"


def test_source_implements_schema_source_protocol():
    """The design source must implement the SchemaSource protocol."""
    source = get_ontology_design_source()
    # Protocol methods
    assert callable(getattr(source, "query_object_types", None))
    assert callable(getattr(source, "query_link_definitions", None))
    assert callable(getattr(source, "query_action_types", None))


def test_source_handles_missing_workspace():
    """Query with missing workspace_id returns empty list (no error)."""
    source = get_ontology_design_source()
    result = source.query_object_types(filters={})
    assert result == []
    result = source.query_link_definitions(filters={})
    assert result == []


def test_source_handles_invalid_entity():
    """get_entity_schema_json with invalid ID returns None."""
    source = get_ontology_design_source()
    result = source.get_entity_schema_json("non-existent-id")
    assert result is None
