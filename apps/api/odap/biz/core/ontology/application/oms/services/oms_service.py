from typing import Dict, Any, List, Optional

from ..storage.sqlite_oms_storage import SQLiteOMSStorage


class OMSService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "OMSService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: SQLiteOMSStorage = None):
        self._storage = storage or SQLiteOMSStorage()

    def list_object_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        return self._storage.list_object_types(active_only=active_only)

    def get_object_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_object_type(type_id)

    def create_object_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_object_type(data)

    def update_object_type(self, type_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._storage.update_object_type(type_id, data)

    def delete_object_type(self, type_id: str) -> bool:
        return self._storage.delete_object_type(type_id)

    def list_action_types(self, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._storage.list_action_types(target_type=target_type)

    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        return self._storage.get_action_type(action_type_id)

    def create_action_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_action_type(data)

    def update_action_type(self, action_type_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._storage.update_action_type(action_type_id, data)

    def delete_action_type(self, action_type_id: str) -> bool:
        return self._storage.delete_action_type(action_type_id)

    def bind_action_to_object_type(self, type_id: str, action_type_id: str) -> bool:
        return self._storage.bind_action_to_object_type(type_id, action_type_id)

    def unbind_action_from_object_type(self, type_id: str, action_type_id: str) -> bool:
        return self._storage.unbind_action_from_object_type(type_id, action_type_id)
