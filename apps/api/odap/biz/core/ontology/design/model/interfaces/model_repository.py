"""
Model Repository Interface (Public)

NOTE: This interface has been aligned with the concrete `ModelRepositoryImpl`
which uses `save_*` (upsert) semantics rather than strict CRUD. The interface
preserves both naming conventions for compatibility.
"""
from typing import Any, Dict, List, Optional


class ModelRepository:
    # ============ Entity Type (upsert semantics) ============

    def save_entity_type(self, entity_type: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an entity type (upsert)."""
        raise NotImplementedError

    def get_entity_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entity type by ID."""
        raise NotImplementedError

    def list_entity_types(
        self,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List entity types in a workspace."""
        raise NotImplementedError

    def delete_entity_type(self, type_id: str) -> bool:
        """Delete an entity type. Returns True if deleted."""
        raise NotImplementedError

    # ============ Instance ============

    def save_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an instance (upsert)."""
        raise NotImplementedError

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get a single instance by ID."""
        raise NotImplementedError

    def list_instances(
        self,
        workspace_id: str,
        entity_type_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List instances in a workspace."""
        raise NotImplementedError

    def delete_instance(self, instance_id: str) -> bool:
        """Delete an instance. Returns True if deleted."""
        raise NotImplementedError

    def batch_import_instances(
        self,
        workspace_id: str,
        entity_type_id: str,
        instances: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Batch import multiple instances. Returns a summary with success/failure counts."""
        raise NotImplementedError
