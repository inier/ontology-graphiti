"""TDD 单元测试：ADR-074 扩展 PROV-O 溯源导出层。

覆盖：
  T-PROV-1: ProvOMapper 映射 Activity/Agent/Entity 三元组
  T-PROV-2: ProvOMapper 按审计项类型补充语义关系（决策→wasDerivedFrom）
  T-PROV-3: AuditExporter CSV 导出
  T-PROV-4: AuditExporter JSON-LD 导出（含 prov:Activity）
  T-PROV-5: AuditExporter Turtle 导出
"""

from __future__ import annotations

import pytest

from odap.infra.security.provenance.prov_o_mapper import ProvOMapper
from odap.infra.security.provenance.audit_exporter import AuditExporter


@pytest.fixture
def audit_event():
    """标准审计事件 dict（决策类）"""
    return {
        "id": "evt-001",
        "event_type": "agent.decision",
        "action": "record_decision",
        "timestamp": "2026-08-20T10:00:00+00:00",
        "actor": {"actor_id": "agent-1", "actor_type": "agent", "actor_name": "决策智能体"},
        "resource": {"resource_type": "decision", "resource_id": "dec-001", "resource_name": "决策1"},
        "workspace_id": "ws1",
    }


@pytest.fixture
def ingest_event():
    """数据采集审计事件"""
    return {
        "id": "evt-002",
        "event_type": "data.ingest",
        "action": "collect",
        "timestamp": "2026-08-20T11:00:00+00:00",
        "actor": {"actor_id": "crawler-1", "actor_type": "system", "actor_name": "爬虫"},
        "resource": {"resource_type": "data", "resource_id": "raw-001", "resource_name": "原始数据"},
        "workspace_id": "ws1",
    }


class TestProvOMapper:
    def test_map_activity_agent_entity(self, audit_event):
        mapped = ProvOMapper().map_event(audit_event)
        assert "activity" in mapped
        assert "agent" in mapped
        assert "entity" in mapped
        # 三元组含 Activity 声明
        triples = mapped["triples"]
        assert any("Activity" in str(t) for t in triples)
        assert any("Agent" in str(t) for t in triples)
        assert any("Entity" in str(t) for t in triples)

    def test_decision_adds_derived_from(self, audit_event):
        mapped = ProvOMapper().map_event(audit_event)
        triples = [str(t) for t in mapped["triples"]]
        assert any("wasDerivedFrom" in t for t in triples)

    def test_ingest_adds_used(self, ingest_event):
        mapped = ProvOMapper().map_event(ingest_event)
        triples = [str(t) for t in mapped["triples"]]
        assert any("used" in t for t in triples)


class TestAuditExporter:
    def test_export_csv(self, audit_event):
        csv_out = AuditExporter().export([audit_event], "csv")
        assert "event_id" in csv_out
        assert "evt-001" in csv_out
        assert "agent.decision" in csv_out

    def test_export_jsonld(self, audit_event):
        content = AuditExporter().export([audit_event], "json-ld")
        # JSON-LD 含 prov:Activity
        assert "Activity" in content or "prov" in content

    def test_export_turtle(self, audit_event):
        content = AuditExporter().export([audit_event], "turtle")
        assert "prov:Activity" in content or "Activity" in content

    def test_export_multiple_events(self, audit_event, ingest_event):
        content = AuditExporter().export([audit_event, ingest_event], "csv")
        assert "evt-001" in content
        assert "evt-002" in content
