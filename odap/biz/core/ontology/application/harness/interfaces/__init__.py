from typing import Dict, Any, List, Optional


class IHarnessService:
    def create_session(self, name: str, description: str = "", scenario_id: Optional[str] = None, workspace_id: Optional[str] = None, requirement: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def get_session(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def advance_stage(self, session_id: str, stage_output: Dict[str, Any] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def fail_stage(self, session_id: str, error: str) -> Dict[str, Any]:
        raise NotImplementedError

    def create_hitl_confirmation(self, session_id: str, stage: str, risk_level: str, title: str, description: str, affected_objects: List[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def resolve_hitl(self, session_id: str, confirmation_id: str, resolution: str, resolved_by: str) -> Dict[str, Any]:
        raise NotImplementedError

    def add_agent_task(self, session_id: str, agent_type: str, stage: str, description: str, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def update_agent_task(self, session_id: str, task_id: str, output_data: Dict[str, Any] = None, status: str = None, error: str = None) -> Dict[str, Any]:
        raise NotImplementedError

    def run_planning(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_ontology_modeling(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_execution(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_full_pipeline(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def approve_step(self, session_id: str, stage: str, approved_by: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def reject_step(self, session_id: str, stage: str, reason: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def create_blueprint(self, name: str, description: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def get_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def list_blueprints(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError
