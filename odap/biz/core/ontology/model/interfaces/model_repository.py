from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ModelRepository(ABC):
    @abstractmethod
    def save_entity_type(self, entity_type: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_entity_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_entity_types(self, filters: Dict[str, Any] = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_entity_type(self, type_id: str) -> bool:
        ...

    @abstractmethod
    def save_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_instances(self, type_id: str = None, workspace_id: str = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        ...

    @abstractmethod
    def batch_import_instances(self, instances: List[Dict[str, Any]]) -> Dict[str, Any]:
        ...
