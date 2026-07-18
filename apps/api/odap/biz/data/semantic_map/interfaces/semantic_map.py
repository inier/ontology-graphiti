from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ISemanticMapGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        name: str,
        ontology_version_id: str,
        ontology_id: str,
        scenario_id: Optional[str] = None,
        description: str = "",
        created_by: str = "system",
        generation_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pass
