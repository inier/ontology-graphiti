import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _reset_singleton():
    from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import BlueprintRuntimeEngine
    BlueprintRuntimeEngine._instance = None
    yield
    BlueprintRuntimeEngine._instance = None


def _make_engine(blueprint_service=None):
    from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import BlueprintRuntimeEngine
    return BlueprintRuntimeEngine(blueprint_service=blueprint_service)


def _make_blueprint_service(blueprint_id="bp-001", name="TestBP", nodes=None, edges=None):
    svc = MagicMock()
    default_nodes = [
        {"node_id": "n1", "node_type": "data_source", "name": "Source"},
        {"node_id": "n2", "node_type": "transform", "name": "Transform"},
        {"node_id": "n3", "node_type": "output", "name": "Output"},
    ]
    default_edges = [
        {"source": "n1", "target": "n2"},
        {"source": "n2", "target": "n3"},
    ]
    svc.get_blueprint.return_value = {
        "status": "success",
        "blueprint_id": blueprint_id,
        "name": name,
        "nodes": nodes if nodes is not None else default_nodes,
        "edges": edges if edges is not None else default_edges,
    }
    return svc


class TestBlueprintRuntimeStart:
    def test_start_execution_success(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        result = engine.start_execution("exec-001", "bp-001")
        assert result["status"] == "success"
        assert result["execution_id"] == "exec-001"
        assert result["execution_status"] == "completed"

    def test_start_execution_blueprint_not_found(self):
        svc = MagicMock()
        svc.get_blueprint.return_value = {"status": "error", "message": "Not found"}
        engine = _make_engine(svc)
        result = engine.start_execution("exec-002", "bp-missing")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_start_execution_no_blueprint_service(self):
        engine = _make_engine(None)
        result = engine.start_execution("exec-003", "bp-001")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_start_execution_empty_nodes(self):
        svc = _make_blueprint_service(nodes=[], edges=[])
        engine = _make_engine(svc)
        result = engine.start_execution("exec-004", "bp-empty")
        assert result["status"] == "error"
        assert "no nodes" in result["message"].lower()

    def test_start_execution_with_metadata(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        result = engine.start_execution("exec-005", "bp-001", metadata={"trigger": "manual"})
        assert result["status"] == "success"
        detail = engine.get_execution("exec-005")
        assert detail["status"] == "success"

    def test_start_execution_execution_order(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        result = engine.start_execution("exec-006", "bp-001")
        assert result["execution_order"] == ["n1", "n2", "n3"]


class TestBlueprintRuntimePauseResume:
    def test_pause_running_execution(self):
        from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import (
            BlueprintExecution, NodeExecution, ExecutionStatus, NodeExecutionState
        )
        engine = _make_engine()
        execution = BlueprintExecution(
            execution_id="exec-010", blueprint_id="bp-001",
            blueprint_name="Test", status=ExecutionStatus.RUNNING,
            node_executions={"n1": NodeExecution(node_id="n1", node_type="data_source")},
            execution_order=["n1"],
        )
        engine._executions["exec-010"] = execution
        result = engine.pause_execution("exec-010")
        assert result["status"] == "success"
        assert result["execution_status"] == "paused"

    def test_pause_nonexistent_execution(self):
        engine = _make_engine()
        result = engine.pause_execution("nonexistent")
        assert result["status"] == "error"

    def test_resume_paused_execution(self):
        from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import (
            BlueprintExecution, NodeExecution, ExecutionStatus, NodeExecutionState
        )
        engine = _make_engine()
        execution = BlueprintExecution(
            execution_id="exec-011", blueprint_id="bp-001",
            blueprint_name="Test", status=ExecutionStatus.PAUSED,
            node_executions={"n1": NodeExecution(node_id="n1", node_type="data_source")},
            execution_order=["n1"],
        )
        engine._executions["exec-011"] = execution
        result = engine.resume_execution("exec-011")
        assert result["status"] == "success"
        assert result["execution_status"] == "completed"

    def test_resume_non_paused_execution_fails(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-012", "bp-001")
        result = engine.resume_execution("exec-012")
        assert result["status"] == "error"


class TestBlueprintRuntimeCancel:
    def test_cancel_execution(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-020", "bp-001")
        result = engine.cancel_execution("exec-020")
        assert result["status"] == "success"
        assert result["execution_status"] == "cancelled"

    def test_cancel_nonexistent_execution(self):
        engine = _make_engine()
        result = engine.cancel_execution("nonexistent")
        assert result["status"] == "error"


class TestBlueprintRuntimeGetAndList:
    def test_get_execution_detail(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-030", "bp-001")
        result = engine.get_execution("exec-030")
        assert result["status"] == "success"
        assert result["execution_id"] == "exec-030"
        assert result["blueprint_id"] == "bp-001"
        assert result["total_steps"] == 3

    def test_get_nonexistent_execution(self):
        engine = _make_engine()
        result = engine.get_execution("nonexistent")
        assert result["status"] == "error"

    def test_list_executions_all(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-040", "bp-001")
        engine.start_execution("exec-041", "bp-001")
        result = engine.list_executions()
        assert result["count"] == 2

    def test_list_executions_filter_by_blueprint(self):
        svc1 = _make_blueprint_service(blueprint_id="bp-a")
        svc2 = _make_blueprint_service(blueprint_id="bp-b")
        engine = _make_engine(svc1)
        engine.start_execution("exec-050", "bp-a")
        engine._blueprint_service = svc2
        engine.start_execution("exec-051", "bp-b")
        result = engine.list_executions(blueprint_id="bp-a")
        assert result["count"] == 1
        assert result["executions"][0]["blueprint_id"] == "bp-a"

    def test_list_executions_filter_by_status(self):
        from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import ExecutionStatus
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-060", "bp-001")
        result = engine.list_executions(status=ExecutionStatus.COMPLETED)
        assert result["count"] == 1


class TestBlueprintRuntimeNodeHandlers:
    def test_register_and_use_handler(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.register_node_handler("data_source", lambda nid, ntype, exe: {"data": "fetched"})
        engine.register_node_handler("transform", lambda nid, ntype, exe: {"transformed": True})
        engine.register_node_handler("output", lambda nid, ntype, exe: {"output": "done"})
        engine.start_execution("exec-070", "bp-001")
        detail = engine.get_execution("exec-070")
        assert detail["execution_status"] == "completed"
        node_states = detail["node_states"]
        assert node_states["n1"]["output"] == {"data": "fetched"}
        assert node_states["n2"]["output"] == {"transformed": True}
        assert node_states["n3"]["output"] == {"output": "done"}

    def test_handler_exception_fails_execution(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.register_node_handler("data_source", lambda nid, ntype, exe: {"ok": True})
        engine.register_node_handler("transform", lambda nid, ntype, exe: (_ for _ in ()).throw(ValueError("bad transform")))
        engine.start_execution("exec-071", "bp-001")
        detail = engine.get_execution("exec-071")
        assert detail["execution_status"] == "failed"
        assert "bad transform" in detail["error"]
        node_states = detail["node_states"]
        assert node_states["n2"]["state"] == "failed"

    def test_no_handler_simulates_node(self):
        svc = _make_blueprint_service()
        engine = _make_engine(svc)
        engine.start_execution("exec-072", "bp-001")
        detail = engine.get_execution("exec-072")
        assert detail["execution_status"] == "completed"
        for nid, ns in detail["node_states"].items():
            assert ns["output"] == {"simulated": True}


class TestBlueprintRuntimeExecutionOrder:
    def test_diamond_dependency_order(self):
        nodes = [
            {"node_id": "a", "node_type": "data_source"},
            {"node_id": "b", "node_type": "transform"},
            {"node_id": "c", "node_type": "transform"},
            {"node_id": "d", "node_type": "output"},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ]
        svc = _make_blueprint_service(nodes=nodes, edges=edges)
        engine = _make_engine(svc)
        result = engine.start_execution("exec-080", "bp-001")
        order = result["execution_order"]
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_disconnected_nodes_appended(self):
        nodes = [
            {"node_id": "n1", "node_type": "data_source"},
            {"node_id": "n2", "node_type": "transform"},
            {"node_id": "n3", "node_type": "output"},
        ]
        edges = [{"source": "n1", "target": "n2"}]
        svc = _make_blueprint_service(nodes=nodes, edges=edges)
        engine = _make_engine(svc)
        result = engine.start_execution("exec-081", "bp-001")
        assert "n3" in result["execution_order"]


class TestBlueprintRuntimeSingleton:
    def test_singleton_pattern(self):
        from odap.biz.core.ontology.application.harness.blueprint.services.blueprint_runtime import BlueprintRuntimeEngine
        a = BlueprintRuntimeEngine.get_instance()
        b = BlueprintRuntimeEngine.get_instance()
        assert a is b
