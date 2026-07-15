import logging
from typing import Dict, Any, List, Optional

from ..storage import SQLiteServitizationStorage
from ..impl.servitization_engine import KnowledgeServitizationEngine

logger = logging.getLogger("servitization_service")


class KnowledgeServitizationService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "KnowledgeServitizationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: SQLiteServitizationStorage = None):
        self.storage = storage or SQLiteServitizationStorage()
        self.engine = KnowledgeServitizationEngine(self.storage)

    def create_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.engine.create_template(data)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def list_templates(self, service_type: Optional[str] = None) -> Dict[str, Any]:
        templates = self.engine.list_templates(service_type=service_type)
        return {"templates": templates, "count": len(templates)}

    def generate_service(self, template_id: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.engine.generate_service(template_id, overrides)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_service(self, service_id: str) -> Dict[str, Any]:
        result = self.engine.get_service(service_id)
        if not result:
            return {"status": "error", "message": f"Service {service_id} not found"}
        return result

    def list_services(self, service_type: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        services = self.engine.list_services(service_type=service_type, status=status)
        return {"services": services, "count": len(services)}

    def deploy_service(self, service_id: str) -> Dict[str, Any]:
        try:
            return self.engine.deploy_service(service_id)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def undeploy_service(self, service_id: str) -> Dict[str, Any]:
        try:
            return self.engine.undeploy_service(service_id)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def generate_from_ontology(self, ontology_id: str, service_type: str = "skill") -> Dict[str, Any]:
        try:
            return self.engine.generate_from_ontology(ontology_id, service_type)
        except Exception as e:
            return {"status": "error", "message": str(e)}
