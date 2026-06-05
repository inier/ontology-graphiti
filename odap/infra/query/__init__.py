"""
Unified Query Service — Entry Point

This package is the canonical entry point for all semantic queries.
Both the design and application subsystems use this service to read
ontology data. Direct cross-boundary imports are forbidden; queries
MUST go through this service.

Usage:
    from odap.infra.query import get_query_service, get_ontology_design_source

    source = get_ontology_design_source()
    rows = source.query_object_types({"workspace_id": "ws-001"})
"""
from .service import QueryService, get_query_service
from .protocols import (
    QuerySource,
    QueryResult,
    SchemaSource,
    EntitySource,
    TopoSource,
    TemporalSource,
)
from .sources import (
    SchemaSourceImpl,
    EntitySourceImpl,
    TopoSourceImpl,
    TemporalSource as TemporalSourceImpl,
)
from .ontology_source import OntologyDesignSource, get_ontology_design_source

__all__ = [
    "QueryService",
    "get_query_service",
    "QuerySource",
    "QueryResult",
    "SchemaSource",
    "EntitySource",
    "TopoSource",
    "TemporalSource",
    "SchemaSourceImpl",
    "EntitySourceImpl",
    "TopoSourceImpl",
    "TemporalSourceImpl",
    "OntologyDesignSource",
    "get_ontology_design_source",
]
