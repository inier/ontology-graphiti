import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..interfaces import IHarnessService
from ..impl import HarnessEngine
from ..storage import SQLiteHarnessStorage
from ..models import HITLRiskLevel

logger = logging.getLogger("harness_service")

HIGH_RISK_OPERATIONS = {"delete", "remove", "bulk_update", "schema_change"}


class HarnessService(IHarnessService):
    _instance = None

    @classmethod
    def get_instance(cls) -> "HarnessService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: SQLiteHarnessStorage = None):
        self._engine = HarnessEngine(storage=storage)

    def create_session(self, name: str, description: str = "", scenario_id: Optional[str] = None, workspace_id: Optional[str] = None, requirement: str = "") -> Dict[str, Any]:
        return self._engine.create_session(name=name, description=description, scenario_id=scenario_id, workspace_id=workspace_id, requirement=requirement)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._engine.get_session(session_id)

    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        return self._engine.list_sessions(status=status, scenario_id=scenario_id)

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        return self._engine.delete_session(session_id)

    def advance_stage(self, session_id: str, stage_output: Dict[str, Any] = None) -> Dict[str, Any]:
        return self._engine.advance_stage(session_id, stage_output=stage_output)

    def fail_stage(self, session_id: str, error: str) -> Dict[str, Any]:
        return self._engine.fail_stage(session_id, error)

    def create_hitl_confirmation(self, session_id: str, stage: str, risk_level: str, title: str, description: str, affected_objects: List[str] = None) -> Dict[str, Any]:
        return self._engine.create_hitl_confirmation(session_id, stage, risk_level, title, description, affected_objects)

    def resolve_hitl(self, session_id: str, confirmation_id: str, resolution: str, resolved_by: str) -> Dict[str, Any]:
        return self._engine.resolve_hitl(session_id, confirmation_id, resolution, resolved_by)

    def add_agent_task(self, session_id: str, agent_type: str, stage: str, description: str, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        return self._engine.add_agent_task(session_id, agent_type, stage, description, input_data)

    def update_agent_task(self, session_id: str, task_id: str, output_data: Dict[str, Any] = None, status: str = None, error: str = None) -> Dict[str, Any]:
        return self._engine.update_agent_task(session_id, task_id, output_data, status, error)

    def update_context(self, session_id: str, key: str, value: Any) -> Dict[str, Any]:
        session_data = self._engine.storage.get_session(session_id)
        if not session_data:
            return {"status": "error", "message": f"Session {session_id} not found"}
        session_data["context_memory"][key] = value
        session_data["updated_at"] = datetime.now().isoformat()
        self._engine.storage.save_session(session_data)
        return {"status": "success"}

    def check_hitl_required(self, operation: str, affected_types: List[str] = None) -> Dict[str, Any]:
        is_high_risk = operation.lower() in HIGH_RISK_OPERATIONS
        risk_level = HITLRiskLevel.HIGH.value if is_high_risk else HITLRiskLevel.LOW.value
        return {
            "operation": operation,
            "hitl_required": is_high_risk,
            "risk_level": risk_level,
            "affected_types": affected_types or [],
        }

    def run_planning(self, session_id: str) -> Dict[str, Any]:
        return self._engine.run_planning(session_id)

    def run_ontology_modeling(self, session_id: str) -> Dict[str, Any]:
        return self._engine.run_ontology_modeling(session_id)

    def run_execution(self, session_id: str) -> Dict[str, Any]:
        return self._engine.run_execution(session_id)

    def run_full_pipeline(self, session_id: str) -> Dict[str, Any]:
        return self._engine.run_full_pipeline(session_id)

    def approve_step(self, session_id: str, stage: str, approved_by: str = "") -> Dict[str, Any]:
        return self._engine.approve_step(session_id, stage, approved_by)

    def reject_step(self, session_id: str, stage: str, reason: str = "") -> Dict[str, Any]:
        return self._engine.reject_step(session_id, stage, reason)

    def create_blueprint(self, name: str, description: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._engine.create_blueprint(name, description, session_id)

    def get_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        return self._engine.get_blueprint(blueprint_id)

    def list_blueprints(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._engine.list_blueprints(session_id)

    def update_blueprint(self, blueprint_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        bp_data = self._engine.storage.get_blueprint(blueprint_id)
        if not bp_data:
            return {"status": "error", "message": f"Blueprint {blueprint_id} not found"}
        for k, v in updates.items():
            if k in bp_data and k != "blueprint_id":
                bp_data[k] = v
        bp_data["version"] = bp_data.get("version", 1) + 1
        return self._engine.storage.save_blueprint(bp_data)

    def delete_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        if self._engine.storage.delete_blueprint(blueprint_id):
            return {"status": "success", "message": f"Blueprint {blueprint_id} deleted"}
        return {"status": "error", "message": f"Blueprint {blueprint_id} not found"}
