from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IHarnessService(ABC):
    @abstractmethod
    def create_session(self, name: str, description: str = "", scenario_id: Optional[str] = None, workspace_id: Optional[str] = None, requirement: str = "") -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_session(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def delete_session(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def advance_stage(self, session_id: str, stage_output: Dict[str, Any] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def fail_stage(self, session_id: str, error: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def create_hitl_confirmation(self, session_id: str, stage: str, risk_level: str, title: str, description: str, affected_objects: List[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def resolve_hitl(self, session_id: str, confirmation_id: str, resolution: str, resolved_by: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def add_agent_task(self, session_id: str, agent_type: str, stage: str, description: str, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def update_agent_task(self, session_id: str, task_id: str, output_data: Dict[str, Any] = None, status: str = None, error: str = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def run_planning(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def run_ontology_modeling(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def run_execution(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def run_full_pipeline(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def approve_step(self, session_id: str, stage: str, approved_by: str = "") -> Dict[str, Any]:
        ...

    @abstractmethod
    def reject_step(self, session_id: str, stage: str, reason: str = "") -> Dict[str, Any]:
        ...

    @abstractmethod
    def create_blueprint(self, name: str, description: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_blueprints(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        ...
