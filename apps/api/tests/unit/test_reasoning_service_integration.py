"""TDD 集成测试：UnifiedReasoningServiceV2.reason() 全链路 (ADR-075)。

Sandbox 策略：
  - tmp_path 真实 DB（rules storage）
  - engine 使用真实 pyDatalog，facts 通过 monkeypatch _load_facts 注入
    （避免依赖真实图库；验证规则入库 → 加载 → 查询 → hybrid 决策链路）

测试用例：
  T-SVC-1: 无规则 → 返回 no_rules（确定性空结果）
  T-SVC-2: 有规则 + facts → 确定性推导成功（source=deterministic）
  T-SVC-3: 规则校验失败入库 → 拒绝（RuleValidationError 冒泡）
  T-SVC-4: 版本快照 + 回滚链路（§3.2）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from odap.biz.core.ontology.reasoning.impl.unified_reasoning_service import (
    UnifiedReasoningServiceV2,
)
from odap.biz.core.ontology.reasoning.rules.models import BusinessRule
from odap.biz.core.ontology.reasoning.rules.storage import SQLiteRuleStorage
from odap.biz.core.ontology.reasoning.engines.deterministic.fact_loader import Fact


@pytest.fixture
def rule_storage(tmp_path: Path) -> SQLiteRuleStorage:
    return SQLiteRuleStorage(db_path=str(tmp_path / "svc_rules.db"))


@pytest.fixture
def svc(rule_storage: SQLiteRuleStorage) -> UnifiedReasoningServiceV2:
    return UnifiedReasoningServiceV2(rule_storage=rule_storage)


def _inject_facts(monkeypatch, facts: list):
    """monkeypatch _load_facts 返回固定 facts，避免真实图库依赖"""
    monkeypatch.setattr(
        UnifiedReasoningServiceV2,
        "_load_facts",
        lambda self, ontology_id, workspace_id, entity_type_ids: facts,
    )


class TestUnifiedReasoningService:
    def test_no_rules_returns_no_rules(self, svc: UnifiedReasoningServiceV2):
        outcome = svc.reason("parent(X, Y)", ontology_id="ont1", workspace_id="ws1")
        assert outcome.source == "deterministic"
        assert outcome.rows == []
        assert outcome.fallback_reason == "no_rules"

    def test_deterministic_success(
        self,
        svc: UnifiedReasoningServiceV2,
        monkeypatch,
    ):
        svc.create_rule(BusinessRule(
            rule_id="r1",
            ontology_id="ont1",
            workspace_id="ws1",
            name="parent_to_ancestor",
            rule_text="ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)",
        ))
        svc.create_rule(BusinessRule(
            rule_id="r2",
            ontology_id="ont1",
            workspace_id="ws1",
            name="base_parent",
            rule_text="ancestor(X, Y) <= parent(X, Y)",
        ))
        _inject_facts(monkeypatch, [
            Fact("parent", ("a", "b")),
            Fact("parent", ("b", "c")),
        ])
        outcome = svc.reason(
            "ancestor(\"a\", X)",
            ontology_id="ont1",
            workspace_id="ws1",
        )
        assert outcome.source == "deterministic"
        assert ("b",) in outcome.rows
        assert ("c",) in outcome.rows

    def test_rule_validation_rejects_dangerous(
        self,
        svc: UnifiedReasoningServiceV2,
    ):
        from odap.biz.core.ontology.reasoning.engines.deterministic.rule_loader import (
            RuleValidationError,
        )
        with pytest.raises(RuleValidationError):
            svc.create_rule(BusinessRule(
                rule_id="evil",
                ontology_id="ont1",
                workspace_id="ws1",
                name="evil_rule",
                rule_text="evil(X) <= parent(X, Y) & eval(Y)",
            ))

    def test_version_snapshot_restore_flow(
        self,
        svc: UnifiedReasoningServiceV2,
        rule_storage: SQLiteRuleStorage,
    ):
        # v1 规则
        svc.create_rule(BusinessRule(
            rule_id="r1", ontology_id="ont1", workspace_id="ws1",
            name="v1", rule_text="a(X) <= b(X)",
        ))
        assert svc.snapshot_rules("v1", "ont1", "ws1") == 1

        # v2 变更
        svc.create_rule(BusinessRule(
            rule_id="r2", ontology_id="ont1", workspace_id="ws1",
            name="v2", rule_text="c(X) <= d(X)",
        ))
        rule_storage.delete("r1")

        # 回滚 v1
        assert svc.restore_rules("v1") == 1
        assert rule_storage.get("r1") is not None
        assert rule_storage.get("r2") is None
