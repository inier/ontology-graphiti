"""版本管理实现"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from ..interfaces.version import IVersionManager
from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
from datetime import datetime

if TYPE_CHECKING:
    from ..models.version import OntologyVersion, VersionChange, OntologyDiff


class VersionManager(IVersionManager):

    def __init__(self):
        self.storage = SQLiteIngestStorage()

    def create_version(self, ontology_id: str, version_number: str,
                      parent_version_id: Optional[str] = None,
                      change_summary: str = "") -> OntologyVersion:
        version = OntologyVersion(
            version_id=f"v{datetime.now().strftime('%Y%m%d')}-001",
            ontology_id=ontology_id,
            version_number=version_number,
            doc_id="",
            doc_type="",
            parent_version=parent_version_id,
            commit_message=change_summary,
            created_at=datetime.now().isoformat(),
        )
        self.storage.save_version({
            'id': version.version_id,
            'ontology_id': version.ontology_id,
            'version_number': version.version_number,
            'parent_version_id': version.parent_version,
            'change_summary': version.commit_message,
            'created_at': version.created_at,
            'is_current': True,
            'is_stable': False,
            'status': 'draft',
        })

        self._update_current_version(ontology_id, version.version_id)

        return version

    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        return self.storage.get_version(version_id)

    def list_versions(self, ontology_id: str,
                     filters: Dict[str, Any] = None,
                     page: int = 1, page_size: int = 10) -> List[OntologyVersion]:
        return self.storage.list_versions(ontology_id, filters, page, page_size)

    def rollback_version(self, ontology_id: str, target_version_id: str) -> OntologyVersion:
        target_version = self.get_version(target_version_id)
        if not target_version:
            raise ValueError("Target version not found")

        new_version = OntologyVersion(
            version_id=f"v{datetime.now().strftime('%Y%m%d')}-001",
            ontology_id=ontology_id,
            version_number=f"{target_version.version_number}-rollback",
            doc_id="",
            doc_type="",
            parent_version=target_version_id,
            commit_message=f"Rollback to version {target_version.version_number}",
            created_at=datetime.now().isoformat(),
        )

        self.storage.save_version({
            'id': new_version.version_id,
            'ontology_id': new_version.ontology_id,
            'version_number': new_version.version_number,
            'parent_version_id': new_version.parent_version,
            'change_summary': new_version.commit_message,
            'created_at': new_version.created_at,
            'is_current': True,
            'is_stable': False,
            'status': 'draft',
        })
        self._update_current_version(ontology_id, new_version.version_id)

        return new_version

    def compare_versions(self, source_version_id: str, target_version_id: str) -> OntologyDiff:
        source_version = self.get_version(source_version_id)
        target_version = self.get_version(target_version_id)

        if not source_version or not target_version:
            raise ValueError("Version not found")

        comparison = OntologyDiff(
            version_a=source_version_id,
            version_b=target_version_id,
        )

        return comparison

    def merge_versions(self, ontology_id: str, source_version_id: str,
                      target_version_id: str, conflict_resolution: Dict[str, Any] = None) -> OntologyVersion:
        source_version = self.get_version(source_version_id)
        target_version = self.get_version(target_version_id)

        if not source_version or not target_version:
            raise ValueError("Version not found")

        new_version = OntologyVersion(
            version_id=f"v{datetime.now().strftime('%Y%m%d')}-001",
            ontology_id=ontology_id,
            version_number=f"{target_version.version_number}-merged",
            doc_id="",
            doc_type="",
            parent_version=target_version_id,
            commit_message=f"Merged with version {source_version.version_number}",
            created_at=datetime.now().isoformat(),
        )

        self.storage.save_version({
            'id': new_version.version_id,
            'ontology_id': new_version.ontology_id,
            'version_number': new_version.version_number,
            'parent_version_id': new_version.parent_version,
            'change_summary': new_version.commit_message,
            'created_at': new_version.created_at,
            'is_current': True,
            'is_stable': False,
            'status': 'draft',
        })
        self._update_current_version(ontology_id, new_version.version_id)

        return new_version

    def get_version_history(self, ontology_id: str) -> List[Dict[str, Any]]:
        versions = self.list_versions(ontology_id)
        history = []

        for version in versions:
            if isinstance(version, dict):
                history.append({
                    "version_id": version.get("id", version.get("version_id", "")),
                    "version_number": version.get("version_number", ""),
                    "status": version.get("status", "draft"),
                    "created_at": version.get("created_at", ""),
                    "change_summary": version.get("change_summary", version.get("commit_message", "")),
                    "is_current": version.get("is_current", False),
                })
            else:
                history.append({
                    "version_id": version.version_id,
                    "version_number": version.version_number,
                    "created_at": version.created_at,
                    "change_summary": version.commit_message,
                    "is_current": version.is_current,
                })

        return history

    def _update_current_version(self, ontology_id: str, current_version_id: str):
        versions = self.list_versions(ontology_id)
        for version in versions:
            if isinstance(version, dict):
                is_current = (version.get("id", version.get("version_id", "")) == current_version_id)
            else:
                is_current = (version.version_id == current_version_id)
            self.storage.update_version(version)
