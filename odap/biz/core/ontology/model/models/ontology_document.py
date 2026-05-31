from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class ActionTypeDefinition(BaseModel):
    action_id: str = ""
    name: str
    target_object_type: str
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    required_roles: List[str] = Field(default_factory=list)
    confirmation_required: bool = False
    opa_policy: Optional[str] = None
    writeback_config: Dict[str, Any] = Field(default_factory=dict)


class OntologyDocument(BaseModel):
    id: str = ""
    name: str
    version: str = "1.0.0"
    object_types: List[Dict[str, Any]] = Field(default_factory=list)
    action_types: List[ActionTypeDefinition] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def to_palantir(self) -> Dict[str, Any]:
        return {
            "ontology": {
                "objectTypes": self.object_types,
                "actionTypes": [a.model_dump() for a in self.action_types],
            },
            "metadata": self.metadata,
        }

    @classmethod
    def from_palantir(cls, data: Dict[str, Any]) -> "OntologyDocument":
        ontology = data.get("ontology", {})
        return cls(
            name=data.get("name", ""),
            object_types=ontology.get("objectTypes", []),
            action_types=[
                ActionTypeDefinition(**a) for a in ontology.get("actionTypes", [])
            ],
            metadata=data.get("metadata", {}),
        )
