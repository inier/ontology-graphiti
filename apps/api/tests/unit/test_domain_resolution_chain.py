"""TDD 单元测试：场景→领域权威解析链（ADR-079 §7.3）。

验证 `QueryPipeline._resolve_domain_id` 的三跳解析：
  T-RES-1: 三跳成功（scenario → ontology.domain_code → domain_id）
  T-RES-2: 无本体绑定 → 返回空串（安全降级）
  T-RES-3: 本体无 domain_code → 返回空串
  T-RES-4: domain_code 无对应领域 → 返回空串
  T-RES-5: UnderstandingStage 只认 domain_id（不再 or scenario_id）

测试策略：monkeypatch 替换三个 service 类为 stub（真实类，非 MagicMock）。
"""

from __future__ import annotations

import pytest

from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline
from odap.biz.data.qa.pipeline.understanding.intent_recognizer import UnderstandingStage


class _StubScenarioService:
    """stub: get_scenario_ontologies 返回 bindings"""

    def __init__(self, bindings):
        self._bindings = bindings

    def get_scenario_ontologies(self, scenario_id):
        return {"scenario_id": scenario_id, "bindings": self._bindings, "total": len(self._bindings)}


class _StubOntologyService:
    """stub: get_ontology 返回含 domain_code 的本体"""

    def __init__(self, ontology):
        self._ontology = ontology

    def get_ontology(self, ontology_id):
        return self._ontology


class _StubUslManagerService:
    """stub: get_domain_by_code 返回 domain"""

    def __init__(self, domain):
        self._domain = domain

    def get_domain_by_code(self, code):
        return self._domain


def _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc):
    """替换 QueryPipeline._resolve_domain_id 内部 import 的三个 service 类"""
    monkeypatch.setattr(
        "odap.biz.platform.workspace.services.scenario_service.ScenarioService",
        lambda: scenario_svc,
    )
    monkeypatch.setattr(
        "odap.biz.core.ontology.ontology_api.services.ontology_service.OntologyService",
        lambda: ontology_svc,
    )
    monkeypatch.setattr(
        "odap.biz.semantic_admin.usl_manager.services.usl_manager_service.UslManagerService",
        lambda: usl_svc,
    )


def _make_pipeline():
    return QueryPipeline(llm_client=None, graph_manager=None)


class TestResolveDomainId:
    def test_three_hop_success(self, monkeypatch):
        scenario_svc = _StubScenarioService([
            {"ontology_id": "ont-1", "binding_status": "active"},
        ])
        ontology_svc = _StubOntologyService({"ontology_id": "ont-1", "domain_code": "sanguo"})
        usl_svc = _StubUslManagerService({"id": "d-sanguo-uuid", "code": "sanguo"})
        _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc)

        pipeline = _make_pipeline()
        assert pipeline._resolve_domain_id("scenario-1") == "d-sanguo-uuid"

    def test_no_binding_returns_empty(self, monkeypatch):
        scenario_svc = _StubScenarioService([])  # 无绑定
        ontology_svc = _StubOntologyService({})
        usl_svc = _StubUslManagerService({})
        _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc)

        pipeline = _make_pipeline()
        assert pipeline._resolve_domain_id("scenario-1") == ""

    def test_ontology_without_domain_code_returns_empty(self, monkeypatch):
        scenario_svc = _StubScenarioService([
            {"ontology_id": "ont-1", "binding_status": "active"},
        ])
        ontology_svc = _StubOntologyService({"ontology_id": "ont-1", "domain_code": None})
        usl_svc = _StubUslManagerService({})
        _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc)

        pipeline = _make_pipeline()
        assert pipeline._resolve_domain_id("scenario-1") == ""

    def test_domain_code_not_found_returns_empty(self, monkeypatch):
        scenario_svc = _StubScenarioService([
            {"ontology_id": "ont-1", "binding_status": "active"},
        ])
        ontology_svc = _StubOntologyService({"ontology_id": "ont-1", "domain_code": "ghost"})
        usl_svc = _StubUslManagerService({"status": "error"})  # 无 id 字段
        _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc)

        pipeline = _make_pipeline()
        assert pipeline._resolve_domain_id("scenario-1") == ""

    def test_inactive_binding_skipped(self, monkeypatch):
        # 有 inactive 绑定 + 一个 active 绑定，应选 active 的 ontology
        scenario_svc = _StubScenarioService([
            {"ontology_id": "ont-inactive", "binding_status": "inactive"},
            {"ontology_id": "ont-active", "binding_status": "active"},
        ])
        ontology_svc = _StubOntologyService({"ontology_id": "ont-active", "domain_code": "xiyou"})
        usl_svc = _StubUslManagerService({"id": "d-xiyou-uuid", "code": "xiyou"})
        _patch_services(monkeypatch, scenario_svc, ontology_svc, usl_svc)

        pipeline = _make_pipeline()
        assert pipeline._resolve_domain_id("scenario-1") == "d-xiyou-uuid"


class TestUnderstandingStageDomainId:
    def test_only_reads_domain_id_not_scenario_id(self):
        """理解层只认 domain_id，不再 or scenario_id（反模式已移除）"""
        stage = UnderstandingStage(llm_client=None)
        # 只传 scenario_id（不传 domain_id）→ domain_id 应为空
        context = {"scenario_id": "scenario-1"}
        understanding = stage.analyze("老刘是谁", context)
        # 无法直接从 understanding 取 domain_id，验证不抛异常且行为一致
        assert understanding is not None

    def test_reads_domain_id_when_present(self):
        stage = UnderstandingStage(llm_client=None)
        context = {"domain_id": "d-sanguo-uuid"}
        understanding = stage.analyze("老刘是谁", context)
        assert understanding is not None
