from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DeploymentRecord:
    deployment_id: str
    service_id: str
    service_name: str
    version: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    endpoint: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_health_check: Optional[str] = None
    error_message: str = ""
    deployed_at: Optional[str] = None
    stopped_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeploymentExecutor:
    _instance: Optional["DeploymentExecutor"] = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._deployments: Dict[str, DeploymentRecord] = {}
        self._health_checkers: Dict[str, callable] = {}

    def deploy(self, deployment_id: str, service_id: str, service_name: str,
               version: str, endpoint: str = "", config: Dict[str, Any] = None,
               metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        record = DeploymentRecord(
            deployment_id=deployment_id, service_id=service_id,
            service_name=service_name, version=version,
            endpoint=endpoint, config=config or {}, metadata=metadata or {}
        )
        self._deployments[deployment_id] = record
        record.status = DeploymentStatus.DEPLOYING
        try:
            deploy_result = self._execute_deploy(record)
            if deploy_result.get("success"):
                record.status = DeploymentStatus.RUNNING
                record.deployed_at = datetime.now().isoformat()
                record.health_status = HealthStatus.HEALTHY
                record.last_health_check = datetime.now().isoformat()
            else:
                record.status = DeploymentStatus.FAILED
                record.error_message = deploy_result.get("error", "Unknown error")
        except Exception as e:
            record.status = DeploymentStatus.FAILED
            record.error_message = str(e)
        return {
            "status": "success", "deployment_id": deployment_id,
            "deployment_status": record.status, "endpoint": record.endpoint
        }

    def stop(self, deployment_id: str) -> Dict[str, Any]:
        if deployment_id not in self._deployments:
            return {"status": "error", "message": "Deployment not found"}
        record = self._deployments[deployment_id]
        if record.status not in (DeploymentStatus.RUNNING, DeploymentStatus.FAILED):
            return {"status": "error", "message": f"Cannot stop deployment in {record.status} state"}
        record.status = DeploymentStatus.STOPPED
        record.stopped_at = datetime.now().isoformat()
        return {"status": "success", "deployment_id": deployment_id, "deployment_status": record.status}

    def rollback(self, deployment_id: str) -> Dict[str, Any]:
        if deployment_id not in self._deployments:
            return {"status": "error", "message": "Deployment not found"}
        record = self._deployments[deployment_id]
        record.status = DeploymentStatus.ROLLING_BACK
        try:
            self._execute_rollback(record)
            record.status = DeploymentStatus.STOPPED
            record.stopped_at = datetime.now().isoformat()
        except Exception as e:
            record.status = DeploymentStatus.FAILED
            record.error_message = str(e)
        return {"status": "success", "deployment_id": deployment_id, "deployment_status": record.status}

    def health_check(self, deployment_id: str) -> Dict[str, Any]:
        if deployment_id not in self._deployments:
            return {"status": "error", "message": "Deployment not found"}
        record = self._deployments[deployment_id]
        if record.status != DeploymentStatus.RUNNING:
            record.health_status = HealthStatus.UNKNOWN
            return {"status": "success", "deployment_id": deployment_id,
                    "health": HealthStatus.UNKNOWN, "message": "Not running"}
        checker = self._health_checkers.get(record.service_id)
        if checker:
            try:
                result = checker(record)
                record.health_status = result.get("health", HealthStatus.UNKNOWN)
                record.last_health_check = datetime.now().isoformat()
            except Exception:
                record.health_status = HealthStatus.UNHEALTHY
                record.last_health_check = datetime.now().isoformat()
        else:
            record.health_status = HealthStatus.HEALTHY
            record.last_health_check = datetime.now().isoformat()
        return {"status": "success", "deployment_id": deployment_id,
                "health": record.health_status, "last_check": record.last_health_check}

    def batch_health_check(self) -> Dict[str, Any]:
        results = {}
        for dep_id in self._deployments:
            if self._deployments[dep_id].status == DeploymentStatus.RUNNING:
                results[dep_id] = self.health_check(dep_id)
        return {"status": "success", "checked_count": len(results), "results": results}

    def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        if deployment_id not in self._deployments:
            return {"status": "error", "message": "Deployment not found"}
        r = self._deployments[deployment_id]
        return {
            "status": "success", "deployment_id": r.deployment_id,
            "service_id": r.service_id, "service_name": r.service_name,
            "version": r.version, "deployment_status": r.status,
            "endpoint": r.endpoint, "health_status": r.health_status,
            "last_health_check": r.last_health_check, "deployed_at": r.deployed_at,
            "error_message": r.error_message
        }

    def list_deployments(self, status: Optional[str] = None) -> Dict[str, Any]:
        records = list(self._deployments.values())
        if status:
            records = [r for r in records if r.status == status]
        return {
            "status": "success", "count": len(records),
            "deployments": [
                {
                    "deployment_id": r.deployment_id, "service_name": r.service_name,
                    "version": r.version, "status": r.status, "health": r.health_status
                }
                for r in records
            ]
        }

    def register_health_checker(self, service_id: str, checker: callable):
        self._health_checkers[service_id] = checker

    def _execute_deploy(self, record: DeploymentRecord) -> Dict[str, Any]:
        return {"success": True}

    def _execute_rollback(self, record: DeploymentRecord):
        pass
