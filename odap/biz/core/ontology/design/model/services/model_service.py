import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..impl.model_repository_impl import ModelRepositoryImpl
from ..models.entity_type import EntityTypeDefinition
from ..models.ontology_document import OntologyDocument


class ModelService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, repository: ModelRepositoryImpl = None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._repo = repository or ModelRepositoryImpl()
        self._initialized = True

    def create_entity_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get("name"):
            return {"status": "error", "message": "name is required"}
        type_id = data.get("type_id") or str(uuid.uuid4())
        data["type_id"] = type_id
        data.setdefault("classification_level", "U")
        self._repo.save_entity_type(data)
        return {"type_id": type_id, "name": data["name"], "classification_level": data["classification_level"]}

    def get_entity_type(self, type_id: str) -> Dict[str, Any]:
        result = self._repo.get_entity_type(type_id)
        if not result:
            return {"status": "error", "message": "Entity type not found"}
        return result

    def list_entity_types(self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        results = self._repo.list_entity_types(filters, page, page_size)
        return {"entity_types": results, "page": page, "page_size": page_size}

    def update_entity_type(self, type_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._repo.get_entity_type(type_id)
        if not existing:
            return {"status": "error", "message": "Entity type not found"}
        existing.update(data)
        existing["type_id"] = type_id
        self._repo.save_entity_type(existing)
        return existing

    def delete_entity_type(self, type_id: str) -> Dict[str, Any]:
        deleted = self._repo.delete_entity_type(type_id)
        if not deleted:
            return {"status": "error", "message": "Entity type not found"}
        return {"status": "ok", "type_id": type_id}

    def create_instance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get("type_id"):
            return {"status": "error", "message": "type_id is required"}
        instance_id = data.get("instance_id") or str(uuid.uuid4())
        data["instance_id"] = instance_id
        now = datetime.now().isoformat()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        data.setdefault("workspace_id", "default")
        self._repo.save_instance(data)
        return {"instance_id": instance_id, "type_id": data["type_id"]}

    def get_instance(self, instance_id: str) -> Dict[str, Any]:
        result = self._repo.get_instance(instance_id)
        if not result:
            return {"status": "error", "message": "Instance not found"}
        return result

    def list_instances(self, type_id: str = None, workspace_id: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        results = self._repo.list_instances(type_id, workspace_id, page, page_size)
        return {"instances": results, "page": page, "page_size": page_size}

    def update_instance(self, instance_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._repo.get_instance(instance_id)
        if not existing:
            return {"status": "error", "message": "Instance not found"}
        existing.update(data)
        existing["instance_id"] = instance_id
        existing["updated_at"] = datetime.now().isoformat()
        self._repo.save_instance(existing)
        return existing

    def delete_instance(self, instance_id: str) -> Dict[str, Any]:
        deleted = self._repo.delete_instance(instance_id)
        if not deleted:
            return {"status": "error", "message": "Instance not found"}
        return {"status": "ok", "instance_id": instance_id}

    def batch_import(self, instances: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._repo.batch_import_instances(instances)

    def validate_instance(self, type_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        type_def = self._repo.get_entity_type(type_id)
        if not type_def:
            return {"status": "error", "message": "Entity type not found"}
        errors = []
        type_props = type_def.get("properties", [])
        for prop_def in type_props:
            if isinstance(prop_def, dict) and prop_def.get("required"):
                prop_name = prop_def.get("name", "")
                if prop_name not in properties or properties[prop_name] is None:
                    errors.append(f"Required property '{prop_name}' is missing")
        if errors:
            return {"status": "error", "message": "Validation failed", "errors": errors}
        return {"status": "ok", "message": "Validation passed"}

    def get_document(self, ontology_id: str) -> Dict[str, Any]:
        from ..storage.sqlite_model_storage import SQLiteModelStorage
        storage = self._repo._storage
        result = storage.get_document(ontology_id)
        if not result:
            return {"status": "error", "message": "Document not found"}
        return result

    def create_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from ..storage.sqlite_model_storage import SQLiteModelStorage
        storage = self._repo._storage
        doc_id = data.get("id") or str(uuid.uuid4())
        data["id"] = doc_id
        now = datetime.now().isoformat()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        storage.save_document(data)
        return {"id": doc_id, "name": data.get("name", "")}

    def export_document(self, ontology_id: str) -> Dict[str, Any]:
        from ..storage.sqlite_model_storage import SQLiteModelStorage
        storage = self._repo._storage
        result = storage.get_document(ontology_id)
        if not result:
            return {"status": "error", "message": "Document not found"}
        doc = OntologyDocument(**result)
        return doc.to_palantir()
