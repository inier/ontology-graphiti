"""
Ontology Design Source — QueryService integration with the design contract.

Bridges the unified query service (`odap.infra.query`) to the design
subsystem's contract layer. Implements the schema source protocol so
that `QueryService` can transparently query ontology schema data.

This is the ONLY place where `odap.infra.query` is allowed to import from
`odap.biz.core.ontology.design.*`. All access goes through `design.contract`.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OntologyDesignSource:
    """
    Adapter implementing the SchemaSource protocol using design/contract.

    This is the canonical bridge between the unified query service and
    the design subsystem. It does NOT import design internals — it goes
    through the public contract.
    """

    _instance: Optional["OntologyDesignSource"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        # Lazy import to keep infra/query independent of biz.core.ontology at module load
        from odap.biz.core.ontology.design.contract import get_design_contract
        self._contract = get_design_contract()

    # ============ SchemaSource protocol implementation ============

    def query_object_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query object types (entity types) by filters.

        Filters supported: workspace_id, ontology_id, version_id, limit, offset
        """
        workspace_id = filters.get("workspace_id")
        if not workspace_id:
            return []
        try:
            entities = self._contract.list_entity_types(
                workspace_id=workspace_id,
                ontology_id=filters.get("ontology_id"),
                version_id=filters.get("version_id"),
                limit=filters.get("limit", 100),
                offset=filters.get("offset", 0),
            )
            return [
                {
                    "object_type_id": e.entity_type_id,
                    "name": e.name,
                    "description": e.description,
                    "workspace_id": e.workspace_id,
                    "ontology_id": e.ontology_id,
                    "version_id": e.version_id,
                    "primary_key_fields": list(e.primary_key_fields),
                    "property_count": len(e.properties),
                }
                for e in entities
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("query_object_types failed: %s", exc)
            return []

    def query_link_definitions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query link definitions (relation types) by filters."""
        workspace_id = filters.get("workspace_id")
        if not workspace_id:
            return []
        try:
            relations = self._contract.list_relation_types(
                workspace_id=workspace_id,
                ontology_id=filters.get("ontology_id"),
                version_id=filters.get("version_id"),
                limit=filters.get("limit", 100),
                offset=filters.get("offset", 0),
            )
            return [
                {
                    "relation_id": r.relation_id,
                    "name": r.name,
                    "description": r.description,
                    "workspace_id": r.workspace_id,
                    "source_entity_type_id": r.source_entity_type_id,
                    "target_entity_type_id": r.target_entity_type_id,
                    "version_id": r.version_id,
                }
                for r in relations
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("query_link_definitions failed: %s", exc)
            return []

    def query_action_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query action types by filters.

        Attempts, in order:
        1. design contract (if it exposes list_action_types)
        2. SQLiteActionStorage (action module's dedicated storage)
        3. SQLiteOntologyStorage (ontology_api's action_type_definitions table)

        Returns empty list when no data source is available — this is a
        graceful degradation, not a placeholder.
        """
        workspace_id = filters.get("workspace_id")
        if not workspace_id:
            return []

        # 1. 尝试通过 design contract 查询
        try:
            if hasattr(self._contract, "list_action_types"):
                actions = self._contract.list_action_types(
                    workspace_id=workspace_id,
                    ontology_id=filters.get("ontology_id"),
                    version_id=filters.get("version_id"),
                    limit=filters.get("limit", 100),
                    offset=filters.get("offset", 0),
                )
                return [
                    {
                        "action_type_id": a.action_type_id if hasattr(a, "action_type_id") else a.get("action_type_id", ""),
                        "name": a.name if hasattr(a, "name") else a.get("name", ""),
                        "description": a.description if hasattr(a, "description") else a.get("description", ""),
                        "workspace_id": workspace_id,
                        "ontology_id": filters.get("ontology_id"),
                        "version_id": filters.get("version_id"),
                    }
                    for a in actions
                ]
        except AttributeError:
            pass
        except Exception as exc:
            logger.warning("query_action_types via contract failed: %s", exc)

        # 2. 降级：从 action 模块的 SQLiteActionStorage 查询
        try:
            from odap.biz.core.ontology.action.storage.sqlite_action_storage import SQLiteActionStorage

            storage = SQLiteActionStorage()
            actions = storage.list_action_types()
            return [
                {
                    "action_type_id": a.get("id", ""),
                    "name": a.get("name", ""),
                    "description": a.get("description", ""),
                    "workspace_id": workspace_id,
                    "ontology_id": filters.get("ontology_id"),
                    "version_id": filters.get("version_id"),
                }
                for a in actions
            ]
        except Exception as exc:
            logger.debug("query_action_types fallback to action storage failed: %s", exc)

        # 3. 降级：从 ontology_api 的 SQLiteOntologyStorage 查询
        try:
            from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import SQLiteOntologyStorage

            storage = SQLiteOntologyStorage()
            ontology_id = filters.get("ontology_id")
            version_id = filters.get("version_id")
            if version_id:
                actions = storage.list_action_types_by_version(version_id)
            elif ontology_id:
                actions = storage.list_action_types(ontology_id)
            else:
                actions = []
            return [
                {
                    "action_type_id": a.get("action_type_id", a.get("id", "")),
                    "name": a.get("name", ""),
                    "description": a.get("description", ""),
                    "workspace_id": workspace_id,
                    "ontology_id": filters.get("ontology_id"),
                    "version_id": filters.get("version_id"),
                }
                for a in actions
            ]
        except Exception as exc:
            logger.debug("query_action_types fallback to ontology_api storage failed: %s", exc)

        return []

    # ============ Additional helpers (not part of protocol) ============

    def get_entity_schema_json(
        self,
        entity_type_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get JSON-Schema description of an entity type via the design contract."""
        try:
            return self._contract.get_entity_type_schema_json(entity_type_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_entity_schema_json failed: %s", exc)
            return None

    def get_ontology(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """Get ontology document by ID."""
        try:
            view = self._contract.get_ontology(ontology_id)
            return {
                "ontology_id": view.ontology_id,
                "name": view.name,
                "workspace_id": view.workspace_id,
                "description": view.description,
                "current_version_id": view.current_version_id,
                "created_at": view.created_at,
                "updated_at": view.updated_at,
                "metadata": dict(view.metadata),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_ontology failed: %s", exc)
            return None

    def list_ontologies(
        self,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List ontologies in a workspace."""
        try:
            views = self._contract.list_ontologies(
                workspace_id=workspace_id, limit=limit, offset=offset
            )
            return [
                {
                    "ontology_id": v.ontology_id,
                    "name": v.name,
                    "workspace_id": v.workspace_id,
                    "current_version_id": v.current_version_id,
                }
                for v in views
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("list_ontologies failed: %s", exc)
            return []


def get_ontology_design_source() -> OntologyDesignSource:
    """Get the singleton design-source adapter for the query service."""
    return OntologyDesignSource()
