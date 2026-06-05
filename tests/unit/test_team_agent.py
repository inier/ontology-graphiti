import pytest
import os
import json
from datetime import datetime
from unittest.mock import patch


def _make_storage(tmp_path):
    from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
    db_path = str(tmp_path / "test_harness.db")
    return SQLiteHarnessStorage(db_path=db_path)


def _make_session(**overrides):
    base = {
        "session_id": "harness-test-001",
        "name": "测试会话",
        "description": "测试描述",
        "requirement": "管理系统需要管理用户和订单，用户创建订单，订单关联商品",
        "planning_output": {},
        "ontology_output": {},
        "execution_output": {},
        "sub_tasks": [],
        "messages": [],
        "context_memory": {},
        "scenario_id": None,
        "workspace_id": None,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    base.update(overrides)
    return base


class TestSQLiteHarnessStorage:
    def test_init_db(self, tmp_path):
        storage = _make_storage(tmp_path)
        assert os.path.exists(storage.db_path)

    def test_save_and_get_session(self, tmp_path):
        storage = _make_storage(tmp_path)
        session = _make_session()
        saved = storage.save_session(session)
        assert saved["session_id"] == "harness-test-001"

        fetched = storage.get_session("harness-test-001")
        assert fetched is not None
        assert fetched["name"] == "测试会话"
        assert fetched["requirement"] == "管理系统需要管理用户和订单，用户创建订单，订单关联商品"

    def test_get_session_not_found(self, tmp_path):
        storage = _make_storage(tmp_path)
        result = storage.get_session("nonexistent")
        assert result is None

    def test_list_sessions(self, tmp_path):
        storage = _make_storage(tmp_path)
        storage.save_session(_make_session(session_id="s1", name="会话1"))
        storage.save_session(_make_session(session_id="s2", name="会话2", status="running"))
        all_sessions = storage.list_sessions()
        assert len(all_sessions) == 2

        running = storage.list_sessions(status="running")
        assert len(running) == 1
        assert running[0]["name"] == "会话2"

    def test_list_sessions_by_scenario(self, tmp_path):
        storage = _make_storage(tmp_path)
        storage.save_session(_make_session(session_id="s1", scenario_id="sc-1"))
        storage.save_session(_make_session(session_id="s2", scenario_id="sc-2"))
        result = storage.list_sessions(scenario_id="sc-1")
        assert len(result) == 1

    def test_delete_session(self, tmp_path):
        storage = _make_storage(tmp_path)
        storage.save_session(_make_session())
        assert storage.delete_session("harness-test-001") is True
        assert storage.get_session("harness-test-001") is None

    def test_delete_session_not_found(self, tmp_path):
        storage = _make_storage(tmp_path)
        assert storage.delete_session("nonexistent") is False

    def test_json_fields_serialization(self, tmp_path):
        storage = _make_storage(tmp_path)
        session = _make_session(
            planning_output={"objects": [{"name": "用户"}]},
            sub_tasks=[{"task_id": "t1", "status": "completed"}],
            messages=[{"message_id": "m1", "from_agent": "planning"}],
            context_memory={"key": "value"},
        )
        storage.save_session(session)
        fetched = storage.get_session("harness-test-001")
        assert fetched["planning_output"]["objects"][0]["name"] == "用户"
        assert len(fetched["sub_tasks"]) == 1
        assert fetched["sub_tasks"][0]["task_id"] == "t1"
        assert len(fetched["messages"]) == 1
        assert fetched["context_memory"]["key"] == "value"

    def test_upsert_session(self, tmp_path):
        storage = _make_storage(tmp_path)
        storage.save_session(_make_session(name="原始"))
        storage.save_session(_make_session(name="更新"))
        fetched = storage.get_session("harness-test-001")
        assert fetched["name"] == "更新"


class TestHarnessModels:
    def test_agent_role_enum(self):
        from odap.biz.core.ontology.application.harness.models import AgentRole
        assert AgentRole.PLANNING.value == "planning"
        assert AgentRole.ONTOLOGY.value == "ontology"
        assert AgentRole.EXECUTOR.value == "executor"
        assert AgentRole.VALIDATOR.value == "validator"

    def test_stage_status_enum(self):
        from odap.biz.core.ontology.application.harness.models import StageStatus
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.HITL_PENDING.value == "hitl_pending"

    def test_agent_message_defaults(self):
        from odap.biz.core.ontology.application.harness.models import AgentMessage
        msg = AgentMessage(from_agent="planning", to_agent="ontology", message_type="result")
        assert msg.message_id.startswith("msg-")
        assert msg.content == {}
        assert msg.timestamp != ""

    def test_sub_task_defaults(self):
        from odap.biz.core.ontology.application.harness.models import SubTask, AgentRole, StageStatus
        task = SubTask(agent_role=AgentRole.PLANNING, description="test")
        assert task.task_id.startswith("task-")
        assert task.status == StageStatus.PENDING
        assert task.input_data == {}
        assert task.output_data == {}
        assert task.dependencies == []
        assert task.error is None
        assert task.completed_at is None

    def test_harness_session_defaults(self):
        from odap.biz.core.ontology.application.harness.models import HarnessSession, StageStatus
        session = HarnessSession(name="test", requirement="req")
        assert session.session_id.startswith("harness-")
        assert session.status == StageStatus.PENDING
        assert session.planning_output == {}
        assert session.sub_tasks == []
        assert session.messages == []
        assert session.context_memory == {}

    def test_requirement_analysis_defaults(self):
        from odap.biz.core.ontology.application.harness.models import RequirementAnalysis
        ra = RequirementAnalysis()
        assert ra.business_objects == []
        assert ra.relationships == []
        assert ra.missing_info == []

    def test_ontology_suggestion_defaults(self):
        from odap.biz.core.ontology.application.harness.models import OntologySuggestion
        os_ = OntologySuggestion()
        assert os_.object_types == []
        assert os_.link_types == []
        assert os_.functions == []
        assert os_.actions == []
        assert os_.constraints == []

    def test_enum_str_inheritance(self):
        from odap.biz.core.ontology.application.harness.models import AgentRole, StageStatus
        assert isinstance(AgentRole.PLANNING, str)
        assert isinstance(StageStatus.PENDING, str)


class TestHarnessServicePipeline:
    def _make_service(self, tmp_path):
        from odap.biz.core.ontology.application.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        return HarnessService(storage=storage)

    def test_create_session(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.create_session(name="测试", requirement="管理用户和订单")
        assert "session_id" in result
        assert result["name"] == "测试"
        assert result["requirement"] == "管理用户和订单"
        assert result["status"] == "pending"

    def test_run_planning(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单，用户创建订单")
        result = service.run_planning(session["session_id"])
        assert result.get("planning_output") != {}
        assert "business_objects" in result["planning_output"]
        assert len(result["sub_tasks"]) >= 1
        assert result["sub_tasks"][-1]["agent_role"] == "planning"

    def test_run_planning_empty_requirement(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="")
        result = service.run_planning(session["session_id"])
        assert result["status"] == "error"

    def test_run_planning_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.run_planning("nonexistent")
        assert result["status"] == "error"

    def test_run_ontology_modeling(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单，用户创建订单")
        service.run_planning(session["session_id"])
        result = service.run_ontology_modeling(session["session_id"])
        assert result.get("ontology_output") != {}
        assert "object_types" in result["ontology_output"]

    def test_run_ontology_modeling_no_planning(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户")
        result = service.run_ontology_modeling(session["session_id"])
        assert result["status"] == "error"

    def test_run_execution(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单，用户创建订单")
        service.run_planning(session["session_id"])
        service.run_ontology_modeling(session["session_id"])
        result = service.run_execution(session["session_id"])
        assert result.get("execution_output") != {}
        assert "workflow" in result["execution_output"]
        assert "blueprint" in result["execution_output"]
        assert result["status"] == "hitl_pending"

    def test_run_execution_no_ontology(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户")
        result = service.run_execution(session["session_id"])
        assert result["status"] == "error"

    def test_run_full_pipeline(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单，用户创建订单，订单关联商品")
        result = service.run_full_pipeline(session["session_id"])
        assert result.get("planning_output") != {}
        assert result.get("ontology_output") != {}
        assert result.get("execution_output") != {}
        assert result["status"] == "hitl_pending"

    def test_get_session(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="req")
        result = service.get_session(session["session_id"])
        assert result["session_id"] == session["session_id"]

    def test_get_session_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.get_session("nonexistent")
        assert result["status"] == "error"

    def test_list_sessions(self, tmp_path):
        service = self._make_service(tmp_path)
        service.create_session(name="s1", requirement="r1")
        service.create_session(name="s2", requirement="r2")
        result = service.list_sessions()
        assert result["count"] == 2

    def test_approve_step(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单")
        service.run_full_pipeline(session["session_id"])
        result = service.approve_step(session["session_id"], "execution")
        assert result["status"] == "completed"

    def test_reject_step(self, tmp_path):
        service = self._make_service(tmp_path)
        session = service.create_session(name="测试", requirement="管理用户和订单")
        service.run_full_pipeline(session["session_id"])
        result = service.reject_step(session["session_id"], "execution", "不符合要求")
        assert result["status"] == "failed"

    def test_approve_step_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.approve_step("nonexistent", "execution")
        assert result["status"] == "error"


class TestHarnessService:
    def test_singleton(self, tmp_path):
        from odap.biz.core.ontology.application.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        HarnessService._instance = None
        svc1 = HarnessService(storage=storage)
        HarnessService._instance = svc1
        svc2 = HarnessService.get_instance()
        assert svc1 is svc2
        HarnessService._instance = None

    def test_service_create_session(self, tmp_path):
        from odap.biz.core.ontology.application.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        svc = HarnessService(storage=storage)
        result = svc.create_session(name="测试", requirement="管理用户")
        assert "session_id" in result

    def test_service_returns_dict(self, tmp_path):
        from odap.biz.core.ontology.application.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        svc = HarnessService(storage=storage)
        result = svc.get_session("nonexistent")
        assert isinstance(result, dict)
        assert result["status"] == "error"


class TestHarnessSchemas:
    def test_create_session_request_validation(self):
        from odap.biz.core.ontology.application.harness.api.schemas import CreateSessionRequest
        req = CreateSessionRequest(name="test", requirement="req")
        assert req.name == "test"
        assert req.description == ""

    def test_create_session_request_min_length(self):
        from odap.biz.core.ontology.application.harness.api.schemas import CreateSessionRequest
        with pytest.raises(Exception):
            CreateSessionRequest(name="", requirement="req")

    def test_approve_step_request(self):
        from odap.biz.core.ontology.application.harness.api.schemas import ApproveStepRequest
        req = ApproveStepRequest(stage="execution", approved_by="admin")
        assert req.stage == "execution"
        assert req.approved_by == "admin"

    def test_reject_step_request(self):
        from odap.biz.core.ontology.application.harness.api.schemas import RejectStepRequest
        req = RejectStepRequest(stage="execution", reason="bad")
        assert req.stage == "execution"
        assert req.reason == "bad"


class TestTeamAgentBackwardCompat:
    def test_team_agent_models_deprecated(self):
        from odap.biz.core.ontology.application.team_agent.models import AgentRole, TaskStatus, TeamSession
        assert AgentRole.PLANNING.value == "planning"
        assert TaskStatus.HITL_PENDING.value == "hitl_pending"
        session = TeamSession(name="test", requirement="req")
        assert session.session_id.startswith("harness-")

    def test_team_agent_engine_deprecated(self, tmp_path):
        from odap.biz.core.ontology.application.team_agent.impl.team_agent_engine import TeamAgentEngine
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        engine = TeamAgentEngine(storage=storage)
        result = engine.create_session(name="测试", requirement="管理用户和订单")
        assert "session_id" in result

    def test_team_agent_service_deprecated(self, tmp_path):
        from odap.biz.core.ontology.application.team_agent.services.team_agent_service import TeamAgentService
        from odap.biz.core.ontology.application.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = SQLiteHarnessStorage(db_path=str(tmp_path / "test.db"))
        svc = TeamAgentService(storage=storage)
        result = svc.create_session(name="测试", requirement="管理用户")
        assert "session_id" in result

    def test_team_agent_storage_deprecated(self, tmp_path):
        from odap.biz.core.ontology.application.team_agent.storage.sqlite_team_agent_storage import SQLiteTeamAgentStorage
        storage = SQLiteTeamAgentStorage(db_path=str(tmp_path / "test.db"))
        assert hasattr(storage, "save_session")
        assert hasattr(storage, "get_session")
