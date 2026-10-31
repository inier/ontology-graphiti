"""F9 HITL 审批与动作执行（AC-41 / AC-42）。

覆盖：低风险免审批、高风险必须审批、审批门 fail-closed（403 / 503）、
执行前置守卫（409 / 404 / 501）、执行后 provenance 闭环。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.contracts import STEP_ORDER
from odap.common.api_errors import ApiError
from qa_action_helpers import (
    SEED_TRACE,
    UNMAPPED,
    USER,
    build_actions,
    propose_all,
    propose_high_risk,
    seed_trace,
)


def _gap_service_patches(monkeypatch, fake):
    monkeypatch.setattr(
        "odap.biz.core.ontology.orchestration.actions.executor._gap_service",
        lambda: fake,
    )
    monkeypatch.setattr(
        "odap.biz.core.ontology.orchestration.actions.executor._gap_source",
        lambda: "mapping_failure",
    )


class TestHitlApproval:
    def test_low_risk_action_needs_no_hitl(self, action_service, trace_repo):
        seed_trace(trace_repo)
        saved = action_service.propose(SEED_TRACE, build_actions(citation_count=1))
        readonly = next(a for a in saved if a.action_type == "view_citations")
        with pytest.raises(ApiError) as exc:
            action_service.decide(readonly.action_id, approved=True, user_ctx=USER)
        assert exc.value.error_code == "ACTION_HITL_NOT_APPLICABLE"
        assert exc.value.status_code == 409

    def test_high_risk_approve_by_authorized_role(self, action_service, trace_repo):
        action = propose_high_risk(action_service, trace_repo)
        decided = action_service.decide(action.action_id, approved=True, user_ctx=USER)
        assert decided["status"] == "approved"
        assert decided["approved_by"] == "u-analyst"

    def test_high_risk_approve_denied_by_policy(self, trace_repo, action_repo,
                                               make_approval_gate):
        from odap.biz.core.ontology.orchestration.actions.service import ActionService

        gate, _client = make_approval_gate(allow=False)
        service = ActionService(repo=action_repo, approval_gate=gate, trace_repo=trace_repo)
        action = propose_high_risk(service, trace_repo)
        with pytest.raises(ApiError) as exc:
            service.decide(action.action_id, approved=True,
                           user_ctx={"sub": "u-viewer", "role": "viewer"})
        assert exc.value.error_code == "APPROVAL_DENIED"
        assert exc.value.status_code == 403
        assert action_repo.get(action.action_id)["status"] == "proposed"

    def test_approval_service_unavailable_is_fail_closed(self, trace_repo, action_repo,
                                                         make_approval_gate):
        from odap.biz.core.ontology.orchestration.actions.service import ActionService

        gate, _client = make_approval_gate(fail=True)
        service = ActionService(repo=action_repo, approval_gate=gate, trace_repo=trace_repo)
        action = propose_high_risk(service, trace_repo)
        with pytest.raises(ApiError) as exc:
            service.decide(action.action_id, approved=True, user_ctx=USER)
        assert exc.value.error_code == "APPROVAL_SERVICE_UNAVAILABLE"
        assert exc.value.status_code == 503
        assert action_repo.get(action.action_id)["status"] == "proposed"

    def test_approval_gate_loads_policy_and_maps_input(self, trace_repo, action_repo,
                                                       make_approval_gate):
        from odap.biz.core.ontology.orchestration.actions.service import ActionService

        gate, client = make_approval_gate(allow=True)
        service = ActionService(repo=action_repo, approval_gate=gate, trace_repo=trace_repo)
        action = propose_high_risk(service, trace_repo)
        service.decide(action.action_id, approved=True,
                       user_ctx={"sub": "u-arch", "role": "schema_auditor",
                                 "ws_role": "domain_editor"})

        assert client.put_calls and client.put_calls[0][0] == "semantic_admin_approval"
        assert "package semantic_admin_approval" in client.put_calls[0][1]
        package, payload = client.eval_calls[0]
        assert package == "semantic_admin_approval"
        assert payload["action"] == "modify"
        assert payload["role"] == "schema_auditor"
        assert payload["ws_role"] == "domain_editor"
        assert payload["candidate"]["action_id"] == action.action_id

    def test_reject_marks_rejected_and_blocks_execution(self, action_service, trace_repo):
        action = propose_high_risk(action_service, trace_repo)
        decided = action_service.decide(action.action_id, approved=False, user_ctx=USER)
        assert decided["status"] == "rejected"
        with pytest.raises(ApiError) as exc:
            action_service.execute(action.action_id)
        assert exc.value.error_code == "ACTION_REJECTED"


class TestExecution:
    def test_high_risk_execute_blocked_before_approval(self, action_service, trace_repo):
        action = propose_high_risk(action_service, trace_repo)
        with pytest.raises(ApiError) as exc:
            action_service.execute(action.action_id)
        assert exc.value.error_code == "ACTION_HITL_REQUIRED"
        assert exc.value.status_code == 409

    def test_low_risk_readonly_executes_and_returns_steps(self, action_service, trace_repo):
        saved = propose_all(action_service, trace_repo)
        action = next(a for a in saved if a.action_type == "open_provenance")
        outcome = action_service.execute(action.action_id)
        assert outcome["action"]["status"] == "executed"
        assert outcome["result"]["step_count"] == 6
        assert [s["step"] for s in outcome["result"]["steps"]] == list(STEP_ORDER)

    def test_gap_fill_executes_after_approval(self, action_service, trace_repo,
                                              monkeypatch, fake_gap_service):
        fake = fake_gap_service()
        _gap_service_patches(monkeypatch, fake)
        action = propose_high_risk(action_service, trace_repo)
        action_service.decide(action.action_id, approved=True, user_ctx=USER)

        outcome = action_service.execute(action.action_id)
        assert outcome["action"]["status"] == "executed"
        assert outcome["result"]["written"] == 1
        assert outcome["result"]["gap_ids"] == ["gap-001"]
        assert fake.calls[0]["expression"] == UNMAPPED[0].raw
        assert fake.calls[0]["ref"] == f"qa_action:{action.payload['trace_id']}"

    def test_gap_fill_write_failure_is_reported(self, action_service, trace_repo,
                                                monkeypatch, fake_gap_service):
        fake = fake_gap_service(ok=False)
        _gap_service_patches(monkeypatch, fake)
        action = propose_high_risk(action_service, trace_repo)
        action_service.decide(action.action_id, approved=True, user_ctx=USER)
        with pytest.raises(ApiError) as exc:
            action_service.execute(action.action_id)
        assert exc.value.error_code == "ACTION_EXECUTION_FAILED"
        assert exc.value.status_code == 502

    def test_unimplemented_action_returns_501(self, action_service, trace_repo):
        saved = propose_all(action_service, trace_repo)
        action = next(a for a in saved if a.action_type == "export_answer_wiki")
        action_service.decide(action.action_id, approved=True, user_ctx=USER)
        with pytest.raises(ApiError) as exc:
            action_service.execute(action.action_id)
        assert exc.value.error_code == "ACTION_EXECUTION_NOT_IMPLEMENTED"
        assert exc.value.status_code == 501

    def test_double_execute_is_rejected(self, action_service, trace_repo):
        saved = propose_all(action_service, trace_repo)
        action = next(a for a in saved if a.action_type == "open_provenance")
        action_service.execute(action.action_id)
        with pytest.raises(ApiError) as exc:
            action_service.execute(action.action_id)
        assert exc.value.error_code == "ACTION_ALREADY_SETTLED"

    def test_unknown_action_id_is_404(self, action_service):
        with pytest.raises(ApiError) as exc:
            action_service.execute("act-01J9ZK8P3Q7N2M4R5T6V7W8X9A")
        assert exc.value.error_code == "ACTION_NOT_FOUND"
