"""
设计契约接口 (Design Contract Interface)

本接口定义应用层对设计层的所有允许访问。
- 只读访问 (Read-only): 应用层 MUST NOT 通过本接口修改设计层数据
- 返回视图对象 (View Objects): 设计层内部模型 MUST NOT 泄漏到应用层
- 通过 ID/字符串引用 (ID References): 实体通过唯一 ID 引用，避免直接对象引用

If application code needs to modify ontology data, it MUST go through
the full design subsystem's own service layer (e.g., during ingestion),
not through this contract.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class ContractError(Exception):
    """Base exception for contract layer errors."""


class ContractNotFoundError(ContractError):
    """Requested resource not found in design layer."""


class ContractValidationError(ContractError):
    """Invalid request parameters."""


@dataclass(frozen=True)
class PropertyView:
    """Immutable view of an entity property — exposed to application layer."""
    name: str
    data_type: str
    is_required: bool = False
    is_primary_key: bool = False
    default_value: Optional[Any] = None
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityTypeView:
    """Immutable view of an entity type — exposed to application layer."""
    entity_type_id: str
    name: str
    description: str
    workspace_id: str
    ontology_id: str
    properties: tuple  # tuple of PropertyView
    primary_key_fields: tuple  # tuple of str
    created_at: str  # ISO format
    updated_at: str  # ISO format
    version_id: str  # Current version this type belongs to
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationTypeView:
    """Immutable view of a relation type — exposed to application layer."""
    relation_id: str
    name: str
    description: str
    workspace_id: str
    source_entity_type_id: str
    target_entity_type_id: str
    properties: tuple  # tuple of PropertyView
    version_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OntologyVersionView:
    """Immutable view of an ontology version."""
    version_id: str
    ontology_id: str
    version_number: str  # e.g., "1.0.0"
    changelog: str
    status: str  # "draft" | "stable" | "archived"
    parent_version_id: Optional[str]
    created_at: str
    created_by: str


@dataclass(frozen=True)
class OntologyDocumentView:
    """Immutable view of an ontology document — exposes summary, not internals."""
    ontology_id: str
    name: str
    workspace_id: str
    description: str
    current_version_id: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class OntologyDesignContract:
    """
    设计层对外契约 (Design Layer Public Contract).

    Application modules MUST depend on this abstraction, NOT on concrete
    design layer implementations. This contract is READ-ONLY.

    The contract returns View Objects (frozen dataclasses) which decouple
    application from internal Pydantic models of the design layer.
    """

    # ============ Entity Type Queries ============

    def get_entity_type(self, entity_type_id: str) -> EntityTypeView:
        """Get a single entity type by ID."""
        raise NotImplementedError

    def list_entity_types(
        self,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EntityTypeView]:
        """List entity types in a workspace, optionally filtered by ontology/version."""
        raise NotImplementedError

    def entity_type_exists(self, entity_type_id: str) -> bool:
        """Check whether an entity type exists."""
        raise NotImplementedError

    # ============ Relation Type Queries ============

    def get_relation_type(self, relation_id: str) -> RelationTypeView:
        """Get a single relation type by ID."""
        raise NotImplementedError

    def list_relation_types(
        self,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RelationTypeView]:
        """List relation types in a workspace."""
        raise NotImplementedError

    # ============ Ontology & Version Queries ============

    def get_ontology(self, ontology_id: str) -> OntologyDocumentView:
        """Get ontology document by ID."""
        raise NotImplementedError

    def list_ontologies(
        self,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OntologyDocumentView]:
        """List ontologies in a workspace."""
        raise NotImplementedError

    def get_version(self, version_id: str) -> OntologyVersionView:
        """Get a specific version by ID."""
        raise NotImplementedError

    def list_versions(self, ontology_id: str) -> List[OntologyVersionView]:
        """List all versions of an ontology."""
        raise NotImplementedError

    def get_current_version(self, ontology_id: str) -> OntologyVersionView:
        """Get the current active version of an ontology."""
        raise NotImplementedError

    # ============ Schema-derived Queries ============

    def get_entity_type_schema_json(
        self,
        entity_type_id: str,
    ) -> Dict[str, Any]:
        """
        Get a JSON-Schema-compatible description of an entity type.

        Returns a dict suitable for validating data against the entity type's
        schema. Application code (e.g., OMS, runtime) uses this to validate
        user inputs without needing direct access to the design models.
        """
        raise NotImplementedError

    def list_property_names(self, entity_type_id: str) -> List[str]:
        """List all property names of an entity type. Useful for validation."""
        raise NotImplementedError
