from abc import ABC, abstractmethod
from typing import Any, Dict


class ValidationEngine(ABC):
    @abstractmethod
    def validate_entity_type(self, type_def: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def validate_instance(self, type_def: Dict[str, Any], properties: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def check_consistency(self, ontology_id: str) -> Dict[str, Any]:
        ...
