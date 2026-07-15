"""
Unified Query Service — Entry Point

This package is the canonical entry point for all semantic queries
and graph write operations. Both the design and application subsystems
use this service to read/write ontology data. Direct cross-boundary
imports of GraphManager are forbidden; reads MUST go through QueryService,
writes MUST go through GraphWriteProxy.

Usage:
    from odap.infra.query import get_query_service, get_ontology_design_source
    from odap.infra.query import get_graph_write_proxy

    source = get_ontology_design_source()
    rows = source.query_object_types({"workspace_id": "ws-001"})

    write_proxy = get_graph_write_proxy()
    write_proxy.add_entity("id-1", "Type", {"key": "value"})
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
    UnstructuredSourceImpl,
)
from .ontology_source import OntologyDesignSource, get_ontology_design_source
from .graph_write_proxy import GraphWriteProxy, get_graph_write_proxy

__all__ = [
    "QueryService",
    "get_query_service",
    "QuerySource",
    "QueryResult",
    "SchemaSource",
    "EntitySource",
    "TopoSource",
    "TemporalSource",
    "UnstructuredSource",
    "SchemaSourceImpl",
    "EntitySourceImpl",
    "TopoSourceImpl",
    "TemporalSourceImpl",
    "UnstructuredSourceImpl",
    "OntologyDesignSource",
    "get_ontology_design_source",
    "GraphWriteProxy",
    "get_graph_write_proxy",
]
