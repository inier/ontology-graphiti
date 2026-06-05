from typing import Any, Dict, List, Optional


class VersionManager:
    def create_version(self, ontology_id: str, changelog: str, valid_time: str = "", snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def get_version(self, ontology_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def compare_versions(self, ontology_id: str, v1_id: str, v2_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def query_at_time(self, ontology_id: str, timestamp: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
