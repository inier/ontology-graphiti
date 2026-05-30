from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IKnowledgeServitizationEngine(ABC):
    @abstractmethod
    def create_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_templates(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def generate_service(self, template_id: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_services(self, service_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def deploy_service(self, service_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def undeploy_service(self, service_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def generate_from_ontology(self, ontology_id: str, service_type: str = "skill") -> Dict[str, Any]:
        ...
