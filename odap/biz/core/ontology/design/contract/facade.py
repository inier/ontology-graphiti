"""
设计契约门面 (Design Contract Facade)

实现 OntologyDesignContract 接口，桥接到设计层内部实现。
This is the only place where application-facing read queries
touch the design layer's internal models.

所有跨边界读取 MUST 通过本类。
"""
import logging
from typing import Any, Dict, List, Optional

from .interface import (
    ContractNotFoundError,
    ContractValidationError,
    EntityTypeView,
    OntologyDesignContract,
    OntologyDocumentView,
    OntologyVersionView,
    PropertyView,
    RelationTypeView,
)

logger = logging.getLogger(__name__)


class DesignContractFacade(OntologyDesignContract):
    """
    单例门面，将 OntologyDesignContract 接口映射到设计层内部服务。
    Singleton facade mapping the contract interface to design-layer internals.

    Lazy-imports the design layer services to avoid circular imports.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        # Lazy imports — see _services()
        self._services_cache: Dict[str, Any] = {}

    # ============ Lazy service accessors ============

    def _services(self):
        """Lazy import of design layer services to avoid circular imports."""
        if "_model" not in self._services_cache:
            from ..model.services.model_service import ModelService
            from ..model.storage.sqlite_model_storage import SQLiteModelStorage

            self._services_cache["_model"] = ModelService(SQLiteModelStorage())
        if "_version" not in self._services_cache:
            from ..version.api.routes import _version_manager
            self._services_cache["_version"] = _version_manager
        return self._services_cache

    # ============ Internal converters ============

    def _to_property_view(self, prop) -> PropertyView:
        """Convert internal property model to PropertyView."""
        return PropertyView(
            name=prop.name,
            data_type=str(getattr(prop, "data_type", "string")),
            is_required=bool(getattr(prop, "is_required", False)),
            is_primary_key=bool(getattr(prop, "is_primary_key", False)),
            default_value=getattr(prop, "default_value", None),
            description=getattr(prop, "description", "") or "",
            constraints=dict(getattr(prop, "constraints", {}) or {}),
        )

    def _to_entity_view(self, entity_doc) -> EntityTypeView:
        """Convert internal entity type model to EntityTypeView."""
        props = tuple(
            self._to_property_view(p) for p in getattr(entity_doc, "properties", []) or []
        )
        pk_fields = tuple(getattr(entity_doc, "primary_key_fields", []) or ())
        return EntityTypeView(
            entity_type_id=entity_doc.id or entity_doc.name,
            name=entity_doc.name,
            description=getattr(entity_doc, "description", "") or "",
            workspace_id=getattr(entity_doc, "workspace_id", ""),
            ontology_id=getattr(entity_doc, "ontology_id", ""),
            properties=props,
            primary_key_fields=pk_fields,
            created_at=str(getattr(entity_doc, "created_at", "")),
            updated_at=str(getattr(entity_doc, "updated_at", "")),
            version_id=getattr(entity_doc, "version_id", ""),
            metadata=dict(getattr(entity_doc, "metadata", {}) or {}),
        )

    def _to_relation_view(self, relation) -> RelationTypeView:
        """Convert internal relation type model to RelationTypeView."""
        props = tuple(
            self._to_property_view(p) for p in getattr(relation, "properties", []) or []
        )
        return RelationTypeView(
            relation_id=relation.id or relation.name,
            name=relation.name,
            description=getattr(relation, "description", "") or "",
            workspace_id=getattr(relation, "workspace_id", ""),
            source_entity_type_id=getattr(relation, "source_entity_type_id", ""),
            target_entity_type_id=getattr(relation, "target_entity_type_id", ""),
            properties=props,
            version_id=getattr(relation, "version_id", ""),
            metadata=dict(getattr(relation, "metadata", {}) or {}),
        )

    def _to_ontology_view(self, doc) -> OntologyDocumentView:
        return OntologyDocumentView(
            ontology_id=doc.id,
            name=getattr(doc, "name", ""),
            workspace_id=getattr(doc, "workspace_id", ""),
            description=getattr(doc, "description", "") or "",
            current_version_id=getattr(doc, "current_version_id", ""),
            created_at=str(getattr(doc, "created_at", "")),
            updated_at=str(getattr(doc, "updated_at", "")),
            metadata=dict(getattr(doc, "metadata", {}) or {}),
        )

    def _to_version_view(self, ver) -> OntologyVersionView:
        return OntologyVersionView(
            version_id=ver.id,
            ontology_id=getattr(ver, "ontology_id", ""),
            version_number=getattr(ver, "version_number", ""),
            changelog=getattr(ver, "changelog", "") or "",
            status=str(getattr(ver, "status", "draft")),
            parent_version_id=getattr(ver, "parent_version_id", None),
            created_at=str(getattr(ver, "created_at", "")),
            created_by=getattr(ver, "created_by", ""),
        )

    # ============ Contract methods ============

    def get_entity_type(self, entity_type_id: str) -> EntityTypeView:
        if not entity_type_id:
            raise ContractValidationError("entity_type_id is required")
        services = self._services()
        entity = services["_model"].get_entity_type(entity_type_id)
        if entity is None:
            raise ContractNotFoundError(f"Entity type not found: {entity_type_id}")
        return self._to_entity_view(entity)

    def list_entity_types(
        self,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EntityTypeView]:
        if not workspace_id:
            raise ContractValidationError("workspace_id is required")
        services = self._services()
        entities = services["_model"].list_entity_types(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version_id=version_id,
            limit=limit,
            offset=offset,
        ) or []
        return [self._to_entity_view(e) for e in entities]

    def entity_type_exists(self, entity_type_id: str) -> bool:
        try:
            self.get_entity_type(entity_type_id)
            return True
        except ContractNotFoundError:
            return False

    def get_relation_type(self, relation_id: str) -> RelationTypeView:
        if not relation_id:
            raise ContractValidationError("relation_id is required")
        services = self._services()
        relation = services["_model"].get_relation_type(relation_id)
        if relation is None:
            raise ContractNotFoundError(f"Relation type not found: {relation_id}")
        return self._to_relation_view(relation)

    def list_relation_types(
        self,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RelationTypeView]:
        if not workspace_id:
            raise ContractValidationError("workspace_id is required")
        services = self._services()
        relations = services["_model"].list_relation_types(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version_id=version_id,
            limit=limit,
            offset=offset,
        ) or []
        return [self._to_relation_view(r) for r in relations]

    def get_ontology(self, ontology_id: str) -> OntologyDocumentView:
        if not ontology_id:
            raise ContractValidationError("ontology_id is required")
        services = self._services()
        doc = services["_model"].get_ontology(ontology_id)
        if doc is None:
            raise ContractNotFoundError(f"Ontology not found: {ontology_id}")
        return self._to_ontology_view(doc)

    def list_ontologies(
        self,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OntologyDocumentView]:
        if not workspace_id:
            raise ContractValidationError("workspace_id is required")
        services = self._services()
        docs = services["_model"].list_ontologies(
            workspace_id=workspace_id, limit=limit, offset=offset
        ) or []
        return [self._to_ontology_view(d) for d in docs]

    def get_version(self, version_id: str) -> OntologyVersionView:
        if not version_id:
            raise ContractValidationError("version_id is required")
        services = self._services()
        ver = services["_version"].get_version(version_id)
        if ver is None:
            raise ContractNotFoundError(f"Version not found: {version_id}")
        return self._to_version_view(ver)

    def list_versions(self, ontology_id: str) -> List[OntologyVersionView]:
        if not ontology_id:
            raise ContractValidationError("ontology_id is required")
        services = self._services()
        versions = services["_version"].list_versions(ontology_id) or []
        return [self._to_version_view(v) for v in versions]

    def get_current_version(self, ontology_id: str) -> OntologyVersionView:
        if not ontology_id:
            raise ContractValidationError("ontology_id is required")
        services = self._services()
        ver = services["_version"].get_current_version(ontology_id)
        if ver is None:
            raise ContractNotFoundError(
                f"No current version found for ontology: {ontology_id}"
            )
        return self._to_version_view(ver)

    def get_entity_type_schema_json(self, entity_type_id: str) -> Dict[str, Any]:
        entity_view = self.get_entity_type(entity_type_id)
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for prop in entity_view.properties:
            properties[prop.name] = {
                "type": prop.data_type,
                "description": prop.description,
                "default": prop.default_value,
            }
            if prop.constraints:
                properties[prop.name]["constraints"] = prop.constraints
            if prop.is_required:
                required.append(prop.name)
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": entity_view.name,
            "type": "object",
            "properties": properties,
            "required": required,
            "x-odap": {
                "entity_type_id": entity_view.entity_type_id,
                "workspace_id": entity_view.workspace_id,
                "ontology_id": entity_view.ontology_id,
                "version_id": entity_view.version_id,
                "primary_key_fields": list(entity_view.primary_key_fields),
            },
        }

    def list_property_names(self, entity_type_id: str) -> List[str]:
        entity_view = self.get_entity_type(entity_type_id)
        return [p.name for p in entity_view.properties]


def get_design_contract() -> OntologyDesignContract:
    """Get the singleton design contract instance."""
    return DesignContractFacade()
