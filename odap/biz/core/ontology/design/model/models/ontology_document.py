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

    def to_owl(self) -> str:
        classes = []
        for ot in self.object_types:
            props = []
            for prop in ot.get("properties", []):
                props.append(f'        <owl:DatatypeProperty rdf:ID="{prop.get("name", "")}">\n            <rdfs:domain rdf:resource="#{ot.get("name", "")}"/>\n            <rdfs:range rdf:resource="&xsd;string"/>\n        </owl:DatatypeProperty>')
            classes.append(f'    <owl:Class rdf:ID="{ot.get("name", "")}"/>\n' + "\n".join(props))
        relations = []
        for rel in self.relations:
            relations.append(f'    <owl:ObjectProperty rdf:ID="{rel.get("name", "")}">\n        <rdfs:domain rdf:resource="#{rel.get("source_type", "")}"/>\n        <rdfs:range rdf:resource="#{rel.get("target_type", "")}"/>\n    </owl:ObjectProperty>')
        return f'<?xml version="1.0"?>\n<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n         xmlns:owl="http://www.w3.org/2002/07/owl#"\n         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"\n         xmlns:xsd="http://www.w3.org/2001/XMLSchema#">\n    <owl:Ontology rdf:about="#{self.name}"/>\n{chr(10).join(classes)}\n{chr(10).join(relations)}\n</rdf:RDF>'

    def to_rdf(self) -> str:
        triples = []
        for ot in self.object_types:
            name = ot.get("name", "")
            triples.append(f'<{self.name}/{name}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .')
            for prop in ot.get("properties", []):
                triples.append(f'<{self.name}/{name}/{prop.get("name", "")}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .')
        for rel in self.relations:
            triples.append(f'<{self.name}/{rel.get("name", "")}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Property> .')
            triples.append(f'<{self.name}/{rel.get("name", "")}> <http://www.w3.org/2000/01/rdf-schema#domain> <{self.name}/{rel.get("source_type", "")}> .')
            triples.append(f'<{self.name}/{rel.get("name", "")}> <http://www.w3.org/2000/01/rdf-schema#range> <{self.name}/{rel.get("target_type", "")}> .')
        return "\n".join(triples)

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
