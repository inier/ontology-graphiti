"""F9 建议动作派生与入库（AC-40 / AC-42）。

覆盖：动作目录的风险分类（高风险必 HITL）、确定性派生规则、`qa_actions` 落库与 trace 关联。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.actions.catalog import ACTION_CATALOG
from odap.common.api_errors import ApiError
from qa_action_helpers import (
    SEED_TRACE,
    QUERY,
    action_types,
    build_actions,
    propose_all,
    seed_trace,
)


class TestActionCatalog:
    def test_high_risk_always_requires_hitl(self):
        for spec in ACTION_CATALOG.values():
            assert spec.risk_level in {"low", "high"}
            if spec.risk_level == "high":
                assert spec.requires_hitl is True, f"{spec.action_type} 高风险却未强制 HITL"

    def test_low_risk_never_requires_hitl(self):
        for spec in ACTION_CATALOG.values():
            if spec.risk_level == "low":
                assert spec.requires_hitl is False


class TestDeriveActions:
    def test_readonly_only_when_actions_disallowed(self):
        actions = build_actions(allow_actions=False, citation_count=2)
        assert action_types(actions) == ["open_provenance", "view_citations"]
        assert all(a.risk_level == "low" for a in actions)
        assert all(a.requires_hitl is False for a in actions)

    def test_high_risk_actions_offered_when_allowed(self):
        actions = build_actions(allow_actions=True, citation_count=1)
        assert "submit_gap_fill" in action_types(actions)
        assert "export_answer_wiki" in action_types(actions)
        gap = next(a for a in actions if a.action_type == "submit_gap_fill")
        assert gap.risk_level == "high"
        assert gap.requires_hitl is True
        assert gap.payload["slots"] == [{"slot": "品类", "raw": "生鲜"}]

    def test_no_answer_skips_export(self):
        actions = build_actions(allow_actions=True, citation_count=0, no_answer=True,
                                unmapped=[])
        assert "export_answer_wiki" not in action_types(actions)
        assert action_types(actions) == ["open_provenance"]

    def test_no_citations_skips_view_citations(self):
        actions = build_actions(allow_actions=False, citation_count=0)
        assert action_types(actions) == ["open_provenance"]

    def test_accepts_dict_unmapped_slots(self):
        actions = build_actions(
            allow_actions=True, citation_count=0, no_answer=True,
            unmapped=[{"slot": "供应商", "raw": "华东仓"}],
        )
        gap = next(a for a in actions if a.action_type == "submit_gap_fill")
        assert gap.payload["slots"] == [{"slot": "供应商", "raw": "华东仓"}]

    def test_unknown_action_type_not_derived(self):
        """目录是风险分类唯一真源：未登记动作不派发（fail-closed）。"""
        from odap.biz.core.ontology.orchestration.actions.catalog import spec_for

        assert spec_for("drop_ontology") is None
        derived = {a.action_type for a in build_actions(allow_actions=True)}
        assert derived <= set(ACTION_CATALOG)


class TestPropose:
    def test_propose_persists_with_trace_link(self, action_service, trace_repo, action_repo):
        saved = propose_all(action_service, trace_repo)
        assert len(saved) == len(action_repo.list_by_trace(SEED_TRACE))
        assert all(a.action_id and a.action_id.startswith("act-") for a in saved)

        rows = action_repo.list_by_trace(SEED_TRACE)
        assert {r["trace_id"] for r in rows} == {SEED_TRACE}
        assert {r["status"] for r in rows} == {"proposed"}
        assert {r["action_type"] for r in rows} == {a.action_type for a in saved}

    def test_propose_on_unknown_trace_is_404(self, action_service):
        with pytest.raises(ApiError) as exc:
            action_service.propose(
                "urn:odap:trace:01AAAAAAAAAAAAAAAAAAAAAAAA", build_actions()
            )
        assert exc.value.error_code == "QA_TRACE_NOT_FOUND"
        assert exc.value.status_code == 404

    def test_propose_keeps_query_and_risk_in_payload(self, action_service, trace_repo):
        seed_trace(trace_repo)
        saved = action_service.propose(SEED_TRACE, build_actions(citation_count=1))
        export = next(a for a in saved if a.action_type == "export_answer_wiki")
        assert export.risk_level == "high"
        assert export.payload["title_suggestion"] == QUERY[:60]
