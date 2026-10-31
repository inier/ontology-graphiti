"""graph_edge 证据校验器（AC-37）。

外部边界（Neo4j）用替身，校验逻辑与 ref 解析走真实实现；
「不可用」分支必须是显式不可解析，不能出现假通过。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.impl.graph_evidence import (
    GraphUnavailableError,
    Neo4jGraphReader,
    parse_graph_ref,
    verify_graph_ref,
)


class RecordingReader:
    """记录查询参数的图读取替身。"""

    def __init__(self, nodes=None, edges=None):
        self.nodes = set(nodes or [])
        self.edges = set(edges or [])
        self.calls: list[tuple] = []

    def node_exists(self, node_id: str) -> bool:
        self.calls.append(("node", node_id))
        return node_id in self.nodes

    def edge_exists(self, source: str, target: str, relation) -> bool:
        self.calls.append(("edge", source, target, relation))
        return (source, target, relation) in self.edges


class BrokenReader:
    def __init__(self, exc: Exception):
        self.exc = exc

    def node_exists(self, node_id: str) -> bool:
        raise self.exc

    def edge_exists(self, source: str, target: str, relation) -> bool:
        raise self.exc


class TestParseGraphRef:
    def test_edge_without_relation_type(self):
        spec = parse_graph_ref("edge:Order-1->Supplier-9")
        assert (spec.kind, spec.source, spec.target, spec.relation) == (
            "edge", "Order-1", "Supplier-9", None,
        )

    def test_edge_with_relation_type(self):
        spec = parse_graph_ref("edge:Order-1-[placedBy]->Supplier-9")
        assert (spec.source, spec.relation, spec.target) == ("Order-1", "PLACEDBY", "Supplier-9")

    def test_relation_type_normalized_to_neo4j_convention(self):
        """关系类型按 infra/graph 写入约定归一：大写 + 空格转下划线。"""
        spec = parse_graph_ref("edge:Order-1-[placed by]->Supplier-9")
        assert spec.relation == "PLACED_BY"

    def test_bare_node_id_from_retrieval_row(self):
        spec = parse_graph_ref("ent-01J9ZK8P3Q7N2M4R5T6V7W8X9A")
        assert (spec.kind, spec.source) == ("node", "ent-01J9ZK8P3Q7N2M4R5T6V7W8X9A")

    @pytest.mark.parametrize("ref", ["node:ent-1", "entity:ent-1", "graph:ent-1"])
    def test_node_prefixes_stripped(self, ref):
        assert parse_graph_ref(ref).source == "ent-1"

    @pytest.mark.parametrize("ref", ["", "   ", "edge:", "edge:Order-1", "edge:->Supplier-9"])
    def test_malformed_rejected(self, ref):
        assert parse_graph_ref(ref) is None


class TestVerifyGraphRef:
    def test_existing_edge_resolves(self):
        reader = RecordingReader(edges={("Order-1", "Supplier-9", None)})
        assert verify_graph_ref("edge:Order-1->Supplier-9", reader=reader) == (True, "")

    def test_missing_edge_reports_reason(self):
        reader = RecordingReader()
        ok, reason = verify_graph_ref("edge:Order-1->Supplier-9", reader=reader)
        assert ok is False and "图中不存在边" in reason

    def test_relation_type_passed_through(self):
        reader = RecordingReader(edges={("Order-1", "Supplier-9", "PLACED_BY")})
        ok, _ = verify_graph_ref("edge:Order-1-[placed_by]->Supplier-9", reader=reader)
        assert ok is True
        assert reader.calls == [("edge", "Order-1", "Supplier-9", "PLACED_BY")]

    def test_relation_type_mismatch_does_not_pass(self):
        reader = RecordingReader(edges={("Order-1", "Supplier-9", "SHIPPED_BY")})
        ok, reason = verify_graph_ref("edge:Order-1-[placed_by]->Supplier-9", reader=reader)
        assert ok is False and "PLACED_BY" in reason

    def test_existing_node_resolves(self):
        reader = RecordingReader(nodes={"ent-1"})
        assert verify_graph_ref("entity:ent-1", reader=reader) == (True, "")

    def test_missing_node_reports_reason(self):
        reader = RecordingReader()
        ok, reason = verify_graph_ref("ent-404", reader=reader)
        assert ok is False and "图中不存在节点" in reason

    def test_reader_unavailable_is_not_a_pass(self):
        reader = BrokenReader(GraphUnavailableError("Neo4j 连接失败: ServiceUnavailable"))
        ok, reason = verify_graph_ref("edge:Order-1->Supplier-9", reader=reader)
        assert ok is False
        assert reason.startswith("GRAPH_UNAVAILABLE")

    def test_reader_crash_is_not_a_pass(self):
        reader = BrokenReader(RuntimeError("Cypher 语法错误"))
        ok, reason = verify_graph_ref("edge:Order-1->Supplier-9", reader=reader)
        assert ok is False
        assert reason.startswith("GRAPH_QUERY_FAILED")


class TestDefaultReader:
    def test_missing_password_blocks_without_network(self):
        """凭据缺失时不发起连接，直接显式不可用（避免测试/CI 卡在 localhost:7687）。"""
        reader = Neo4jGraphReader(uri="bolt://localhost:7687", user="neo4j", password="")
        ok, reason = verify_graph_ref("edge:Order-1->Supplier-9", reader=reader)
        assert ok is False
        assert reason.startswith("GRAPH_UNAVAILABLE")
        assert "NEO4J_PASSWORD" in reason


class TestResolverIntegration:
    def test_default_resolver_uses_neo4j_verifier(self, tbox_catalog, monkeypatch):
        from odap.biz.core.ontology.orchestration import evidence as evidence_module
        from odap.biz.core.ontology.orchestration.impl import graph_evidence

        reader = RecordingReader(edges={("Order-1", "Supplier-9", None)})
        monkeypatch.setattr(graph_evidence, "default_graph_reader", lambda: reader)

        resolver = evidence_module.DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("graph_edge", "edge:Order-1->Supplier-9") == (True, "")
        ok, reason = resolver.resolve("graph_edge", "edge:Order-9->Supplier-404")
        assert ok is False and "图中不存在边" in reason

    def test_injected_verifier_still_wins(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(
            catalog=tbox_catalog, graph_verifier=lambda ref: (True, ""),
        )
        assert resolver.resolve("graph_edge", "edge:A->B") == (True, "")
