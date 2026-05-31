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

    def get_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_audit(audit_id)

    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        return self._storage.list_audits(entity_type_id, page, page_size)
