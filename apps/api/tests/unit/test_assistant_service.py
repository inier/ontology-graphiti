"""T061 [TDD] AssistantService tests.

Tests for AG-UI protocol handler: run/resume flow, tool_call dispatch, HITL.
"""
import json

import pytest


@pytest.fixture
def service(tmp_path):
    from odap.biz.core.ontology.assistant.services.assistant_service import (
        AssistantService,
    )
    db_path = str(tmp_path / "test_assistant_service.db")
    return AssistantService(db_path=db_path)


class TestHealthCheck:
    def test_health_check_returns_status(self, service):
        result = service.health_check()
        assert "status" in result
        assert "llm_available" in result
        assert "rule_engine_available" in result
        assert result["rule_engine_available"] is True
        assert result["ag_ui_protocol"] == "v1"


class TestInferType:
    def test_infer_type_delegates_to_engine(self, service):
        result = service.infer_type("email")
        assert result["inferred_type"] == "STRING"
        assert result["source"] == "rule_engine"

    def test_infer_type_age(self, service):
        result = service.infer_type("age")
        assert result["inferred_type"] == "INTEGER"


class TestSuggestConstraints:
    def test_suggest_constraints_email(self, service):
        result = service.suggest_constraints("email", "STRING")
        assert result["constraints"].get("format") == "email"

    def test_suggest_constraints_age(self, service):
        result = service.suggest_constraints("age", "INTEGER")
        assert result["constraints"].get("minimum") == 0


class TestCreateSession:
    def test_create_session_returns_session_id(self, service):
        result = service.create_session(
            ontology_id="ont-001",
            user_id="user-001",
            context_type="object_type_editor",
            context_id="type-user",
        )
        assert "session_id" in result
        assert result["status"] == "active"
        assert result["ontology_id"] == "ont-001"

    def test_get_session_existing(self, service):
        created = service.create_session(
            ontology_id="ont-001",
            user_id="user-001",
            context_type="object_type_editor",
        )
        sid = created["session_id"]
        result = service.get_session(sid)
        assert result["session_id"] == sid

    def test_get_session_nonexistent_returns_error(self, service):
        result = service.get_session("nonexistent")
        assert result.get("status") == "error"


class TestRunFlow:
    @pytest.mark.asyncio
    async def test_run_add_property_creates_suggestion(self, service):
        events = []
        async for event in service.run(
            ontology_id="ont-001",
            context_type="object_type_editor",
            message="添加一个 email 属性",
            context_id="type-user-001",
            user_id="user-001",
        ):
            events.append(event)
        assert any(e["type"] == "RUN_STARTED" for e in events)
        assert any(e["type"] == "TOOL_CALL_START" for e in events)
        assert any(e["type"] == "TOOL_CALL_END" for e in events)
        finished = [e for e in events if e["type"] == "RUN_FINISHED"]
        assert len(finished) == 1
        assert "interrupts" in finished[0]
        assert finished[0]["interrupts"][0]["type"] == "hitl"

    @pytest.mark.asyncio
    async def test_run_suggest_properties_no_hitl(self, service):
        events = []
        async for event in service.run(
            ontology_id="ont-001",
            context_type="object_type_editor",
            message="推荐属性",
            context_id="type-user-001",
            user_id="user-001",
        ):
            events.append(event)
        finished = [e for e in events if e["type"] == "RUN_FINISHED"]
        assert len(finished) == 1
        assert "interrupts" not in finished[0] or not finished[0].get("interrupts")

    @pytest.mark.asyncio
    async def test_run_unknown_intent_returns_error_message(self, service):
        events = []
        async for event in service.run(
            ontology_id="ont-001",
            context_type="object_type_editor",
            message="xyz unknown command",
            context_id="type-user-001",
            user_id="user-001",
        ):
            events.append(event)
        content_events = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert len(content_events) > 0
        assert "无法识别" in content_events[0]["delta"] or "无法处理" in content_events[0]["delta"]


class TestResumeFlow:
    @pytest.mark.asyncio
    async def test_resume_approved_accepts_suggestion(self, service):
        events = []
        async for event in service.run(
            ontology_id="ont-001",
            context_type="object_type_editor",
            message="添加一个 email 属性",
            context_id="type-user-001",
            user_id="user-001",
        ):
            events.append(event)
        finished = [e for e in events if e["type"] == "RUN_FINISHED"][0]
        suggestion_id = finished["interrupts"][0]["suggestion_id"]
        resume_events = []
        async for event in service.resume(
            run_id="run-001",
            tool_call_id="tc-001",
            response="approved",
            suggestion_id=suggestion_id,
            user_id="user-001",
        ):
            resume_events.append(event)
        content_events = [e for e in resume_events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert len(content_events) > 0
        assert "已确认" in content_events[0]["delta"]

    @pytest.mark.asyncio
    async def test_resume_rejected_rejects_suggestion(self, service):
        events = []
        async for event in service.run(
            ontology_id="ont-001",
            context_type="object_type_editor",
            message="添加一个 email 属性",
            context_id="type-user-001",
            user_id="user-001",
        ):
            events.append(event)
        finished = [e for e in events if e["type"] == "RUN_FINISHED"][0]
        suggestion_id = finished["interrupts"][0]["suggestion_id"]
        resume_events = []
        async for event in service.resume(
            run_id="run-001",
            tool_call_id="tc-001",
            response="rejected",
            suggestion_id=suggestion_id,
            user_id="user-001",
        ):
            resume_events.append(event)
        content_events = [e for e in resume_events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert len(content_events) > 0
        assert "已取消" in content_events[0]["delta"]
