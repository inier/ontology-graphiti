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

    @abstractmethod
    def record_ingest_audit(self, entity_type_id: str, source: str, process_steps: List[Dict[str, Any]], transform_rules: List[Dict[str, Any]], result: str, source_type: str = "", process_details: List[Dict[str, Any]] = None, transform_details: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def list_audits_filtered(self, entity_type_id: str = None, source: str = None, source_type: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        ...
