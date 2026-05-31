from typing import Any, Dict, List, Optional

from ..interfaces.model_repository import ModelRepository
from ..storage.sqlite_model_storage import SQLiteModelStorage


class ModelRepositoryImpl(ModelRepository):
    def __init__(self, storage: SQLiteModelStorage = None):
        self._storage = storage or SQLiteModelStorage()

    def save_entity_type(self, entity_type: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.save_entity_type(entity_type)

    def get_entity_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_entity_type(type_id)

    def list_entity_types(
        self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20
    ) -> List[Dict[str, Any]]:
        return self._storage.list_entity_types(filters, page, page_size)

    def delete_entity_type(self, type_id: str) -> bool:
        return self._storage.delete_entity_type(type_id)

    def save_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.save_instance(instance)

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_instance(instance_id)

    def list_instances(
        self,
        type_id: str = None,
        workspace_id: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        return self._storage.list_instances(type_id, workspace_id, page, page_size)

    def delete_instance(self, instance_id: str) -> bool:
        return self._storage.delete_instance(instance_id)

    def batch_import_instances(
        self, instances: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self._storage.batch_import_instances(instances)
