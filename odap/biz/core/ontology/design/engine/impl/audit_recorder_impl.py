import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces.audit_recorder import AuditRecorder
from ..storage.sqlite_engine_storage import SQLiteEngineStorage


class AuditRecorderImpl(AuditRecorder):
    def __init__(self, storage: SQLiteEngineStorage = None):
        self._storage = storage or SQLiteEngineStorage()

    def record_ingest(self, entity_type_id: str, source: str, process_steps: List[Dict[str, Any]], transform_rules: List[Dict[str, Any]], result: str) -> Dict[str, Any]:
        audit_id = str(uuid.uuid4())
        audit = {
            "audit_id": audit_id,
            "entity_type_id": entity_type_id,
            "source": source,
            "process_steps": process_steps,
            "transform_rules": transform_rules,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self._storage.save_audit(audit)
        return audit

    def record_ingest_audit(self, entity_type_id: str, source: str, process_steps: List[Dict[str, Any]], transform_rules: List[Dict[str, Any]], result: str, source_type: str = "", process_details: List[Dict[str, Any]] = None, transform_details: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        audit_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        merged_process_steps = list(process_steps or [])
        if process_details:
            merged_process_steps.extend(process_details)

        merged_transform_rules = list(transform_rules or [])
        if transform_details:
            merged_transform_rules.extend(transform_details)

        if source_type:
            source_meta = {"source_type": source_type}
            if merged_process_steps:
                merged_process_steps.insert(0, {"step": "source_classification", "source_type": source_type, "timestamp": now})
            else:
                merged_process_steps = [{"step": "source_classification", "source_type": source_type, "timestamp": now}]

        audit = {
            "audit_id": audit_id,
            "entity_type_id": entity_type_id,
            "source": source,
            "source_type": source_type,
            "process_steps": merged_process_steps,
            "transform_rules": merged_transform_rules,
            "result": result,
            "timestamp": now,
        }
        self._storage.save_ingest_audit(audit)
        return audit

    def get_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_audit(audit_id)
        if result:
            return result
        return self._storage.get_ingest_audit(audit_id)

    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        return self._storage.list_audits(entity_type_id, page, page_size)

    def list_audits_filtered(self, entity_type_id: str = None, source: str = None, source_type: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        return self._storage.list_ingest_audits(entity_type_id, source, source_type, page, page_size)

    def record_audit(self, ontology_id: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Record an audit entry (ABC implementation)."""
        return self.record_ingest(
            entity_type_id=ontology_id,
            source=action,
            process_steps=[details] if details else [],
            transform_rules=[],
            result="recorded",
        )

    def get_audit_logs(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Get audit logs (ABC implementation)."""
        return self.list_audits(entity_type_id=ontology_id, page=page, page_size=page_size)
