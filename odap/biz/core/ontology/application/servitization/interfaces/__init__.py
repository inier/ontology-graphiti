from typing import Dict, Any, List, Optional


class IKnowledgeServitizationEngine:
    def create_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def list_templates(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def generate_service(self, template_id: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def list_services(self, service_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def deploy_service(self, service_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def undeploy_service(self, service_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_from_ontology(self, ontology_id: str, service_type: str = "skill") -> Dict[str, Any]:
        raise NotImplementedError
