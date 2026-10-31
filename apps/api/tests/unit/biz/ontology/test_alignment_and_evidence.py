"""本体对齐与证据解析测试（AC-26 / AC-27 / AC-37 / AC-38）。

- 对齐只接受 TBox 里真实存在的元素，映射不到进 `unmapped[]`（不静默丢弃、不猜）。
- 证据解析必须逐类可判定：可解析给出肯定，不可解析必须给出具体原因（不假通过）。
"""

from __future__ import annotations

import pytest

from odap.common.api_errors import ApiError
from odap.biz.core.ontology.orchestration.contracts import IntentFrame
from odap.biz.core.ontology.orchestration.impl.ontology_aligner import TBoxOntologyAligner


class TestTBoxCatalog:
    def test_lookup_hits_by_name_and_returns_kind_ref(self, tbox_catalog):
        ref, element = tbox_catalog.lookup("退货率", "ws-supply")
        assert ref == "metric:order_return_rate"
        assert element["kind"] == "metric"
        assert tbox_catalog.lookup("订单", "ws-supply")[0] == "ObjectType:Order"
        assert tbox_catalog.lookup("下单方", "ws-supply")[0] == "RelationType:placedBy"

    def test_lookup_miss_returns_none(self, tbox_catalog):
        assert tbox_catalog.lookup("渠道库存周转天数", "ws-supply") is None

    def test_exists_checks_kind_and_id(self, tbox_catalog):
        assert tbox_catalog.exists("ObjectType", "Order", "ws-supply") is True
        assert tbox_catalog.exists("ObjectType", "Invoice", "ws-supply") is False
        assert tbox_catalog.exists("metric", "order_return_rate", "ws-supply") is True

    def test_snapshot_hash_is_deterministic_and_prefixed(self, tbox_catalog):
        first = tbox_catalog.snapshot_hash("ws-supply")
        second = tbox_catalog.snapshot_hash("ws-supply")
        assert first == second
        assert first.startswith("sha256:") and len(first) == 71

    def test_snapshot_hash_differs_across_workspaces_with_different_data(
            self, fake_ontology_service):
        from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

        class _OtherService(fake_ontology_service):
            def list_indicator_types(self, ontology_id):
                return {"indicator_types": [{"id": "order_return_rate", "name": "退货率"}]}

        base = TBoxCatalog(ontology_service_factory=lambda: fake_ontology_service())
        other = TBoxCatalog(ontology_service_factory=lambda: _OtherService())
        assert base.snapshot_hash("ws-supply") != other.snapshot_hash("ws-supply")


class TestAligner:
    async def test_maps_known_terms(self, tbox_catalog):
        aligner = TBoxOntologyAligner(tbox_catalog)
        intent = IntentFrame(intent_type="metric_query", confidence=0.95,
                             slots={"terms": ["退货率", "订单"]})
        mapped = await aligner.align(intent, "ws-supply")
        assert [r.ref for r in mapped.metrics] == ["metric:order_return_rate"]
        assert [r.ref for r in mapped.object_types] == ["ObjectType:Order"]
        assert mapped.unmapped == []
        kinds = {e.kind for e in mapped.prov.evidence}
        assert kinds == {"tbox_node"}

    async def test_unknown_term_goes_to_unmapped_with_decision(self, tbox_catalog):
        aligner = TBoxOntologyAligner(tbox_catalog)
        intent = IntentFrame(intent_type="concept_lookup", confidence=0.95,
                             slots={"terms": ["渠道库存周转天数"]})
        mapped = await aligner.align(intent, "ws-supply")
        assert mapped.object_types == []
        assert [u.raw for u in mapped.unmapped] == ["渠道库存周转天数"]
        refs = [e.ref for e in mapped.prov.evidence]
        assert "decision:unmapped_to_gap_pool" in refs

    async def test_unreadable_tbox_fails_closed(self):
        from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

        class _Broken:
            def list_ontologies(self, workspace_id=None):
                return {"status": "error", "message": "SQLite 文件损坏"}

        aligner = TBoxOntologyAligner(TBoxCatalog(ontology_service_factory=lambda: _Broken()))
        with pytest.raises(ApiError) as excinfo:
            await aligner.align(IntentFrame(intent_type="metric_query"), "ws-supply")
        assert excinfo.value.error_code == "TBOX_UNAVAILABLE"
        assert excinfo.value.status_code == 503


class TestEvidenceResolver:
    def test_tbox_node_resolves(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("tbox_node", "ObjectType:Order") == (True, "")
        ok, reason = resolver.resolve("tbox_node", "ObjectType:Invoice")
        assert ok is False and "不存在" in reason

    def test_metric_ignores_time_suffix(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("metric", "metric:order_return_rate@2026Q3") == (True, "")
        ok, reason = resolver.resolve("metric", "metric:gross_margin@2026Q3")
        assert ok is False and "不存在" in reason

    def test_metric_rejects_non_metric_element(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        ok, reason = resolver.resolve("metric", "metric:订单")
        assert ok is False and "不是指标类型" in reason

    def test_opa_decision_requires_real_policy_file(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("opa_decision", "policies/ontology_assistant.rego#allow")[0] is True
        ok, reason = resolver.resolve("opa_decision", "policies/missing.rego#allow")
        assert ok is False and "策略规则不存在" in reason

    def test_decision_must_be_known_enum(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("decision", "decision:no_evidence") == (True, "")
        ok, reason = resolver.resolve("decision", "decision:trust_me_bro")
        assert ok is False and "未知决策枚举" in reason

    def test_doc_uses_injected_verifier(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(
            catalog=tbox_catalog,
            doc_verifier=lambda ref: (True, "") if ref == "doc-01JABC" else (False, "文档不存在"),
        )
        assert resolver.resolve("doc", "doc-01JABC") == (True, "")
        assert resolver.resolve("doc", "doc-gone")[0] is False

    def test_graph_edge_unverifiable_without_backend(self, tbox_catalog, monkeypatch):
        from odap.biz.core.ontology.orchestration import evidence as evidence_module
        from odap.biz.core.ontology.orchestration.impl import graph_evidence

        def _unavailable():
            raise graph_evidence.GraphUnavailableError("Neo4j 连接失败（测试环境未提供图后端）")

        monkeypatch.setattr(graph_evidence, "default_graph_reader", _unavailable)

        resolver = evidence_module.DefaultEvidenceResolver(catalog=tbox_catalog)
        ok, reason = resolver.resolve("graph_edge", "edge:Order-1->Supplier-9")
        assert ok is False
        assert reason.startswith("GRAPH_UNAVAILABLE")  # 显式不可解析，不假装通过

    def test_graph_edge_resolves_with_verifier(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(
            catalog=tbox_catalog, graph_verifier=lambda ref: (True, "")
        )
        assert resolver.resolve("graph_edge", "edge:Order-1->Supplier-9") == (True, "")

    def test_empty_ref_and_unknown_kind_rejected(self, tbox_catalog):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver(catalog=tbox_catalog)
        assert resolver.resolve("doc", "  ") == (False, "ref 为空")
        ok, reason = resolver.resolve("screenshot", "img-1")
        assert ok is False and "未知证据种类" in reason
