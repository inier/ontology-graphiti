import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _reset_singleton():
    from odap.biz.core.ontology.application.servitization.services.deployment_executor import DeploymentExecutor
    DeploymentExecutor._instance = None
    yield
    DeploymentExecutor._instance = None


def _make_executor():
    from odap.biz.core.ontology.application.servitization.services.deployment_executor import DeploymentExecutor
    return DeploymentExecutor()


class TestDeploymentExecutorDeploy:
    def test_deploy_success(self):
        executor = _make_executor()
        result = executor.deploy(
            deployment_id="dep-001", service_id="svc-001",
            service_name="TestService", version="1.0.0"
        )
        assert result["status"] == "success"
        assert result["deployment_id"] == "dep-001"
        assert result["deployment_status"] == "running"

    def test_deploy_with_endpoint_and_config(self):
        executor = _make_executor()
        result = executor.deploy(
            deployment_id="dep-002", service_id="svc-002",
            service_name="Service2", version="2.0.0",
            endpoint="http://localhost:8080", config={"replicas": 3},
            metadata={"env": "prod"}
        )
        assert result["status"] == "success"
        assert result["endpoint"] == "http://localhost:8080"
        detail = executor.get_deployment("dep-002")
        assert detail["status"] == "success"

    def test_deploy_failure_when_execute_fails(self):
        executor = _make_executor()
        def _fail_deploy(record):
            raise RuntimeError("Deploy failed")
        executor._execute_deploy = _fail_deploy
        result = executor.deploy(
            deployment_id="dep-003", service_id="svc-003",
            service_name="FailService", version="1.0.0"
        )
        assert result["status"] == "success"
        assert result["deployment_status"] == "failed"
        detail = executor.get_deployment("dep-003")
        assert detail["error_message"] == "Deploy failed"

    def test_deploy_returns_not_success(self):
        executor = _make_executor()
        def _reject_deploy(record):
            return {"success": False, "error": "Rejected by policy"}
        executor._execute_deploy = _reject_deploy
        result = executor.deploy(
            deployment_id="dep-004", service_id="svc-004",
            service_name="RejectService", version="1.0.0"
        )
        assert result["deployment_status"] == "failed"
        detail = executor.get_deployment("dep-004")
        assert detail["error_message"] == "Rejected by policy"


class TestDeploymentExecutorStop:
    def test_stop_running_deployment(self):
        executor = _make_executor()
        executor.deploy("dep-010", "svc-010", "RunningService", "1.0.0")
        result = executor.stop("dep-010")
        assert result["status"] == "success"
        assert result["deployment_status"] == "stopped"

    def test_stop_nonexistent_deployment(self):
        executor = _make_executor()
        result = executor.stop("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_stop_pending_deployment_fails(self):
        executor = _make_executor()
        from odap.biz.core.ontology.application.servitization.services.deployment_executor import (
            DeploymentRecord, DeploymentStatus
        )
        record = DeploymentRecord(
            deployment_id="dep-011", service_id="svc-011",
            service_name="PendingService", version="1.0.0"
        )
        record.status = DeploymentStatus.PENDING
        executor._deployments["dep-011"] = record
        result = executor.stop("dep-011")
        assert result["status"] == "error"
        assert "Cannot stop" in result["message"]


class TestDeploymentExecutorRollback:
    def test_rollback_success(self):
        executor = _make_executor()
        executor.deploy("dep-020", "svc-020", "RollbackService", "1.0.0")
        result = executor.rollback("dep-020")
        assert result["status"] == "success"
        assert result["deployment_status"] == "stopped"

    def test_rollback_nonexistent(self):
        executor = _make_executor()
        result = executor.rollback("nonexistent")
        assert result["status"] == "error"

    def test_rollback_failure_sets_failed(self):
        executor = _make_executor()
        executor.deploy("dep-021", "svc-021", "FailRollback", "1.0.0")
        def _fail_rollback(record):
            raise RuntimeError("Rollback crashed")
        executor._execute_rollback = _fail_rollback
        result = executor.rollback("dep-021")
        assert result["deployment_status"] == "failed"
        detail = executor.get_deployment("dep-021")
        assert detail["error_message"] == "Rollback crashed"


class TestDeploymentExecutorHealthCheck:
    def test_health_check_running_no_checker(self):
        executor = _make_executor()
        executor.deploy("dep-030", "svc-030", "HealthyService", "1.0.0")
        result = executor.health_check("dep-030")
        assert result["status"] == "success"
        assert result["health"] == "healthy"

    def test_health_check_with_custom_checker(self):
        executor = _make_executor()
        executor.deploy("dep-031", "svc-031", "CheckedService", "1.0.0")
        executor.register_health_checker("svc-031", lambda r: {"health": "degraded"})
        result = executor.health_check("dep-031")
        assert result["health"] == "degraded"

    def test_health_check_checker_exception(self):
        executor = _make_executor()
        executor.deploy("dep-032", "svc-032", "BadChecker", "1.0.0")
        executor.register_health_checker("svc-032", lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
        result = executor.health_check("dep-032")
        assert result["health"] == "unhealthy"

    def test_health_check_nonexistent(self):
        executor = _make_executor()
        result = executor.health_check("nonexistent")
        assert result["status"] == "error"

    def test_health_check_not_running(self):
        executor = _make_executor()
        executor.deploy("dep-033", "svc-033", "StoppedService", "1.0.0")
        executor.stop("dep-033")
        result = executor.health_check("dep-033")
        assert result["health"] == "unknown"

    def test_batch_health_check(self):
        executor = _make_executor()
        executor.deploy("dep-040", "svc-040", "Service1", "1.0.0")
        executor.deploy("dep-041", "svc-041", "Service2", "1.0.0")
        executor.stop("dep-041")
        result = executor.batch_health_check()
        assert result["checked_count"] == 1
        assert "dep-040" in result["results"]


class TestDeploymentExecutorListAndGet:
    def test_get_deployment_detail(self):
        executor = _make_executor()
        executor.deploy("dep-050", "svc-050", "DetailService", "2.0.0",
                        endpoint="http://api.example.com")
        result = executor.get_deployment("dep-050")
        assert result["status"] == "success"
        assert result["service_name"] == "DetailService"
        assert result["version"] == "2.0.0"
        assert result["endpoint"] == "http://api.example.com"

    def test_get_nonexistent_deployment(self):
        executor = _make_executor()
        result = executor.get_deployment("nonexistent")
        assert result["status"] == "error"

    def test_list_deployments_all(self):
        executor = _make_executor()
        executor.deploy("dep-060", "svc-060", "A", "1.0.0")
        executor.deploy("dep-061", "svc-061", "B", "2.0.0")
        result = executor.list_deployments()
        assert result["count"] == 2

    def test_list_deployments_filter_by_status(self):
        executor = _make_executor()
        executor.deploy("dep-070", "svc-070", "Running", "1.0.0")
        executor.deploy("dep-071", "svc-071", "AlsoRunning", "1.0.0")
        executor.stop("dep-071")
        from odap.biz.core.ontology.application.servitization.services.deployment_executor import DeploymentStatus
        result = executor.list_deployments(status=DeploymentStatus.RUNNING)
        assert result["count"] == 1
        assert result["deployments"][0]["deployment_id"] == "dep-070"

    def test_singleton_pattern(self):
        from odap.biz.core.ontology.application.servitization.services.deployment_executor import DeploymentExecutor
        a = DeploymentExecutor.get_instance()
        b = DeploymentExecutor.get_instance()
        assert a is b
