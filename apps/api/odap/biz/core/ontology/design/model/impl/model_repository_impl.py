import uuid
from typing import Any, Dict, List, Optional

from ..interfaces.model_repository import ModelRepository
from ..models.entity_type import EntityTypeDefinition, PropertyDefinition
from ..storage.sqlite_model_storage import SQLiteModelStorage


class ModelRepositoryImpl(ModelRepository):
    def __init__(self, storage: SQLiteModelStorage = None):
        self._storage = storage or SQLiteModelStorage()

    def save_entity_type(self, entity_type: Dict[str, Any]) -> Dict[str, Any]:
        name = entity_type.get("name", "").strip()
        if not name:
            raise ValueError("Entity type name is required")

        existing = self._storage.list_entity_types({"name": name}, page=1, page_size=100)
        type_id = entity_type.get("type_id", "")
        for item in existing:
            if item.get("name") == name and item.get("type_id") != type_id:
                raise ValueError(f"Entity type with name '{name}' already exists")

        properties = entity_type.get("properties", [])
        self._validate_properties(properties)

        primary_key = entity_type.get("primary_key", [])
        if primary_key:
            prop_names = {p.get("name") for p in properties}
            for pk_field in primary_key:
                if pk_field not in prop_names:
                    raise ValueError(f"Primary key field '{pk_field}' not found in properties")

        if not type_id:
            entity_type["type_id"] = str(uuid.uuid4())

        return self._storage.save_entity_type(entity_type)

    def get_entity_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        if not type_id:
            return None
        return self._storage.get_entity_type(type_id)

    def list_entity_types(
        self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20
    ) -> List[Dict[str, Any]]:
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        return self._storage.list_entity_types(filters, page, page_size)

    def delete_entity_type(self, type_id: str) -> bool:
        if not type_id:
            return False
        instances = self._storage.list_instances(type_id=type_id, page=1, page_size=1)
        if instances:
            raise ValueError(f"Cannot delete entity type '{type_id}': has associated instances")
        return self._storage.delete_entity_type(type_id)

    def save_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        type_id = instance.get("type_id", "")
        if not type_id:
            raise ValueError("Instance must specify type_id")

        entity_type = self._storage.get_entity_type(type_id)
        if not entity_type:
            raise ValueError(f"Entity type '{type_id}' not found")

        properties = instance.get("properties", {})
        self._validate_instance_properties(entity_type, properties)

        primary_key = entity_type.get("primary_key", [])
        if primary_key:
            self._check_instance_uniqueness(entity_type, properties, primary_key, instance.get("instance_id", ""))

        instance_id = instance.get("instance_id", "")
        if not instance_id:
            instance["instance_id"] = str(uuid.uuid4())

        return self._storage.save_instance(instance)

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        if not instance_id:
            return None
        return self._storage.get_instance(instance_id)

    def list_instances(
        self,
        type_id: str = None,
        workspace_id: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        return self._storage.list_instances(type_id, workspace_id, page, page_size)

    def delete_instance(self, instance_id: str) -> bool:
        if not instance_id:
            return False
        return self._storage.delete_instance(instance_id)

    def batch_import_instances(
        self, instances: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        success_count = 0
        fail_count = 0
        errors = []

        for i, instance in enumerate(instances):
            try:
                self.save_instance(instance)
                success_count += 1
            except (ValueError, Exception) as e:
                fail_count += 1
                errors.append({"row": i, "error": str(e)})

        return {
            "total": len(instances),
            "success": success_count,
            "failed": fail_count,
            "errors": errors,
        }

    def _validate_properties(self, properties: List[Dict[str, Any]]) -> None:
        names = set()
        for prop in properties:
            name = prop.get("name", "").strip()
            if not name:
                raise ValueError("Property name is required")
            if name in names:
                raise ValueError(f"Duplicate property name: '{name}'")
            names.add(name)

    def _validate_instance_properties(
        self, entity_type: Dict[str, Any], instance_props: Dict[str, Any]
    ) -> None:
        et_props = entity_type.get("properties", [])
        for prop_def in et_props:
            if prop_def.get("required", False):
                prop_name = prop_def.get("name", "")
                if prop_name not in instance_props or instance_props[prop_name] is None:
                    raise ValueError(f"Required property '{prop_name}' is missing")

    def _check_instance_uniqueness(
        self,
        entity_type: Dict[str, Any],
        properties: Dict[str, Any],
        primary_key: List[str],
        exclude_id: str = "",
    ) -> None:
        existing = self._storage.list_instances(
            type_id=entity_type.get("type_id"), page=1, page_size=1000
        )
        pk_values = tuple(properties.get(k) for k in primary_key)
        for inst in existing:
            if inst.get("instance_id") == exclude_id:
                continue
            inst_props = inst.get("properties", {})
            inst_pk = tuple(inst_props.get(k) for k in primary_key)
            if inst_pk == pk_values:
                raise ValueError(
                    f"Instance with primary key {dict(zip(primary_key, pk_values))} already exists"
                )
