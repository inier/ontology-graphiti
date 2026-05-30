import warnings
warnings.warn(
    "ITeamAgentService is deprecated. Use HarnessService instead.",
    DeprecationWarning,
    stacklevel=2,
)
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ITeamAgentService(ABC):
    @abstractmethod
    def create_session(self, name: str, requirement: str, description: str = "",
                       scenario_id: Optional[str] = None, workspace_id: Optional[str] = None) -> Dict[str, Any]:
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
    def get_session(self, session_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_sessions(self, status: Optional[str] = None, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def approve_step(self, session_id: str, step: str, comment: str = "") -> Dict[str, Any]:
        ...

    @abstractmethod
    def reject_step(self, session_id: str, step: str, reason: str = "") -> Dict[str, Any]:
        ...
