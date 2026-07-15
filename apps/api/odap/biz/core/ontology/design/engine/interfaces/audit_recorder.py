from typing import Any, Dict, List, Optional


class AuditRecorder:
    def record_audit(self, ontology_id: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def get_audit_logs(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        raise NotImplementedError
