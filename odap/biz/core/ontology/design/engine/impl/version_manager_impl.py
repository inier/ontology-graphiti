import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces.version_manager import VersionManager
from ..storage.sqlite_engine_storage import SQLiteEngineStorage


class VersionManagerImpl(VersionManager):
    def __init__(self, storage: SQLiteEngineStorage = None):
        self._storage = storage or SQLiteEngineStorage()

    def create_version(self, ontology_id: str, changelog: str, valid_time: str = "", snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        version_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        version = {
            "version_id": version_id,
            "ontology_id": ontology_id,
            "version_number": self._next_version_number(ontology_id),
            "changelog": changelog,
            "valid_time": valid_time or now,
            "transaction_time": now,
            "status": "active",
            "snapshot": snapshot or {},
        }
        self._storage.save_version(version)
        return version

    def get_version(self, ontology_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        version = self._storage.get_version(version_id)
        if version and version.get("ontology_id") == ontology_id:
            return version
        return None

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        return self._storage.list_versions(ontology_id, page, page_size)

    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        target = self._storage.get_version(target_version_id)
        if not target or target.get("ontology_id") != ontology_id:
            return {"status": "error", "message": "Target version not found"}
        rollback = self.create_version(
            ontology_id=ontology_id,
            changelog=f"Rollback to version {target.get('version_number', '')}",
            valid_time=datetime.now().isoformat(),
            snapshot=target.get("snapshot", {}),
        )
        rollback["status"] = "rolled_back"
        self._storage.save_version(rollback)
        return rollback

    def compare_versions(self, ontology_id: str, v1_id: str, v2_id: str) -> Dict[str, Any]:
        v1 = self._storage.get_version(v1_id)
        v2 = self._storage.get_version(v2_id)
        if not v1 or not v2:
            return {"status": "error", "message": "One or both versions not found"}
        return {
            "v1": {"version_id": v1_id, "version_number": v1.get("version_number"), "snapshot": v1.get("snapshot", {})},
            "v2": {"version_id": v2_id, "version_number": v2.get("version_number"), "snapshot": v2.get("snapshot", {})},
        }

    def query_at_time(self, ontology_id: str, timestamp: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_version_at_time(ontology_id, timestamp)

    def _next_version_number(self, ontology_id: str) -> str:
        versions = self._storage.list_versions(ontology_id, page=1, page_size=1)
        if not versions:
            return "1.0.0"
        latest = versions[0].get("version_number", "1.0.0")
        try:
            parts = latest.split(".")
            patch = int(parts[-1]) + 1
            return ".".join(parts[:-1] + [str(patch)])
        except (ValueError, IndexError):
            return "1.0.0"
