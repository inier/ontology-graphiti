from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AuditRecorder(ABC):
    @abstractmethod
    def record_ingest(self, entity_type_id: str, source: str, process_steps: List[Dict[str, Any]], transform_rules: List[Dict[str, Any]], result: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        ...
