"""Unit tests for UnstructuredSource and QueryService .unstructured support."""
import pytest

from odap.infra.query.protocols import QuerySource
from odap.infra.query.sources.unstructured_source import UnstructuredSourceImpl


class FakeUnstructuredRetriever:
    def __init__(self, objects=None):
        self._objects = objects or []
        self.calls = []

    async def retrieve(self, query, top_k=10):
        self.calls.append((query, top_k))
        class R:
            def __init__(self, objects):
                self.objects = objects
        return R(self._objects)


class TestUnstructuredSource:
    def test_search_success(self):
        objs = [
            type("O", (), {
                "id": "1", "object_id": "obj-1", "object_type": "Person",
                "score": 0.95, "description": "Alice", "links": []
            })(),
            type("O", (), {
                "id": "2", "object_id": "obj-2", "object_type": "Person",
                "score": 0.85, "description": "Bob", "links": []
            })(),
        ]
        retriever = FakeUnstructuredRetriever(objs)
        src = UnstructuredSourceImpl(retriever=retriever)
        rows = src.search("alice", workspace_id="ws-1", ontology_id="ont-1", limit=5)
        assert len(rows) == 2
        assert rows[0]["object_id"] == "obj-1"
        assert rows[0]["workspace_id"] == "ws-1"
        assert rows[0]["ontology_id"] == "ont-1"

    def test_search_empty(self):
        retriever = FakeUnstructuredRetriever([])
        src = UnstructuredSourceImpl(retriever=retriever)
        rows = src.search("nothing")
        assert rows == []

    def test_search_error_handling(self):
        class Boom:
            def retrieve(self, q, top_k=10):
                raise RuntimeError("vector store down")

        # Build a retriever-like object
        class BadRetriever:
            def retrieve(self, q, top_k=10):
                raise RuntimeError("vector store down")

        src = UnstructuredSourceImpl(retriever=BadRetriever())
        rows = src.search("query")
        assert len(rows) == 1
        assert "error" in rows[0]

    def test_query_source_enum_has_unstructured(self):
        assert QuerySource.UNSTRUCTURED == "unstructured"

    def test_query_parser_supports_unstructured_prefix(self):
        from odap.infra.query.parser import QueryParser
        parsed = QueryParser().parse(".unstructured with(query='hello')")
        assert parsed.source == QuerySource.UNSTRUCTURED
        assert parsed.filters.get("query") == "hello"
