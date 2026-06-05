import warnings
warnings.warn(
    "ITeamAgentService is deprecated. Use HarnessService instead.",
    DeprecationWarning,
    stacklevel=2,
)
from typing import Dict, Any, Optional


class ITeamAgentService:
    def create_session(self, name: str, requirement: str, description: str = "",
                       scenario_id: Optional[str] = None, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def run_planning(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_ontology_modeling(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_execution(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_full_pipeline(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_session(self, session_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def approve_step(self, session_id: str, step: str, comment: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def reject_step(self, session_id: str, step: str, reason: str = "") -> Dict[str, Any]:
        raise NotImplementedError
