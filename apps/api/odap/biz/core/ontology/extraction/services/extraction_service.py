"""Extraction service — delegates HE-based extraction to data.hyper_extract.ExtractService.

This service now serves as a thin compatibility layer:
- Database extraction (test_database_connection, extract_from_database) remains here
  since it uses DatabaseSchemaExtractor, not HE.
- All HE-based extraction (NL, document, KB, confirm, get_session) delegates to
  the new ExtractService at odap.biz.data.hyper_extract.services.extract_service.

Follows AGENTS.md Rule 2: returns Dict[str, Any], never raises HTTPException.
"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.ontology_api.services import OntologyService

try:
    from odap.infra.security.unified_audit import UnifiedAudit

    _audit_available = True
except ImportError:
    _audit_available = False

logger = logging.getLogger(__name__)


def _audit(action: str, user_id: str = None, resource_type: str = "extraction", resource_id: str = None, details: Dict[str, Any] = None):
    if _audit_available:
        UnifiedAudit.log_action(action=action, user_id=user_id, resource_type=resource_type, resource_id=resource_id, details=details or {})
    else:
        logger.info("AUDIT | action=%s | user_id=%s | resource_type=%s | resource_id=%s | details=%s", action, user_id, resource_type, resource_id, details)


class ExtractionService:
    """Orchestrates extraction sessions.

    HE-based extraction methods delegate to the new ExtractService in
    odap.biz.data.hyper_extract. Database extraction remains here.
    """

    def __init__(self, db_path: str = None):
        self.ontology_service = OntologyService(db_path=db_path)
        # Lazy-init the new ExtractService to avoid circular imports at module load
        self._he_extract_service = None

    @property
    def he_service(self):
        """Lazy-load the new ExtractService from data.hyper_extract."""
        if self._he_extract_service is None:
            from odap.biz.data.hyper_extract.services.extract_service import ExtractService
            self._he_extract_service = ExtractService()
        return self._he_extract_service

    # ------------------------------------------------------------------
    # Database extraction (no HE — stays here)
    # ------------------------------------------------------------------

    def test_database_connection(
        self,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str = None,
        password: str = None,
    ) -> Dict[str, Any]:
        """Test database connection.

        Returns:
            Dict with keys: status, message, table_count, schema_name
        """
        from odap.biz.core.ontology.design.ingestion_split.db_schema_ingester import (
            DatabaseSchemaExtractor,
        )

        extractor = DatabaseSchemaExtractor()
        return extractor.test_connection(db_type, host, port, database, username, password)

    def extract_from_database(
        self,
        ontology_id: str,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str = None,
        password: str = None,
        table_filter: List[str] = None,
        use_llm_enrichment: bool = False,
    ) -> Dict[str, Any]:
        """Extract schema from database and create extraction session.

        This method does NOT use Hyper-Extract. It uses DatabaseSchemaExtractor
        to introspect the database schema directly.

        Returns:
            Dict with keys: status, session_id, result, conflicts
        """
        # 1. Create session via OntologyService
        session_result = self.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="database",
            input_data={"db_type": db_type, "host": host, "database": database},
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        # 2. Extract
        from odap.biz.core.ontology.design.ingestion_split.db_schema_ingester import (
            DatabaseSchemaExtractor,
        )

        extractor = DatabaseSchemaExtractor()
        result = extractor.extract_schema(
            db_type, host, port, database, username, password,
            table_filter, use_llm_enrichment,
        )

        if result.get("status") == "error":
            self.ontology_service.update_extraction_session(
                session_id,
                {"status": "failed", "result_data": result},
            )
            return result

        # 3. Detect conflicts with existing types
        conflicts = self._detect_conflicts(ontology_id, result)

        # 4. Update session
        self.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "reviewing",
                "result_data": result,
                "conflicts": conflicts,
            },
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "result": result,
            "conflicts": conflicts,
        }

    # ------------------------------------------------------------------
    # HE-based extraction (delegated to new ExtractService)
    # ------------------------------------------------------------------

    async def extract_from_nl(
        self,
        ontology_id: str,
        text: str,
        auto_search: bool = False,
        template_id: str = None,
        method: str = None,
        mode: str = None,
    ) -> Dict[str, Any]:
        """Extract schema from natural language text.

        Delegates to data.hyper_extract.ExtractService.extract_from_nl()
        which provides full orchestration: assess → select → multi-parse →
        LLM supplement → merge → validate → conflicts → finalize.

        Args:
            mode: Optional mode flag. When "schema_learning", enhances schema inference.
        """
        _audit(
            "extraction_nl_start",
            resource_id=ontology_id,
            details={"text_length": len(text), "auto_search": auto_search, "template_id": template_id, "method": method, "mode": mode},
        )
        result = await self.he_service.extract_from_nl(
            text=text,
            ontology_id=ontology_id,
            template_id=template_id,
            method=method,
            mode=mode,
        )
        _audit(
            "extraction_nl_complete",
            resource_id=ontology_id,
            details={
                "session_id": result.get("session_id", ""),
                "status": result.get("status", ""),
                "template_used": result.get("template_used", ""),
            },
        )
        return result

    async def extract_from_document(
        self,
        ontology_id: str,
        file_path: str,
        template_id: str = None,
        method: str = None,
        mode: str = None,
    ) -> Dict[str, Any]:
        """Extract schema from a document file.

        Delegates to data.hyper_extract.ExtractService.extract_from_document()
        which handles document parsing, chunking, and per-chunk multi-parse.

        Args:
            mode: Optional mode flag. When "schema_learning", enhances schema inference.
        """
        _audit(
            "extraction_document_start",
            resource_id=ontology_id,
            details={"file_path": file_path, "template_id": template_id, "method": method, "mode": mode},
        )
        result = await self.he_service.extract_from_document(
            file_path=file_path,
            ontology_id=ontology_id,
            template_id=template_id,
            method=method,
            mode=mode,
        )
        _audit(
            "extraction_document_complete",
            resource_id=ontology_id,
            details={
                "session_id": result.get("session_id", ""),
                "status": result.get("status", ""),
            },
        )
        return result

    async def extract_from_knowledge_base(
        self,
        ontology_id: str,
        kb_id: str,
        template_id: str = None,
        method: str = None,
        document_ids: List[str] = None,
        batch_size: int = 5,
        mode: str = None,
    ) -> Dict[str, Any]:
        """Extract schema from a knowledge base.

        Delegates to data.hyper_extract.ExtractService.extract_from_knowledge_base()
        which iterates KB documents, chunks each, and runs multi-parse per chunk.

        Args:
            mode: Optional mode flag. When "schema_learning", enhances schema inference.
        """
        _audit(
            "extraction_kb_start",
            resource_id=ontology_id,
            details={"kb_id": kb_id, "template_id": template_id, "document_ids": document_ids, "mode": mode},
        )
        result = await self.he_service.extract_from_knowledge_base(
            ontology_id=ontology_id,
            kb_id=kb_id,
            template_id=template_id,
            method=method,
            document_ids=document_ids,
            mode=mode,
        )
        _audit(
            "extraction_kb_complete",
            resource_id=ontology_id,
            details={
                "session_id": result.get("session_id", ""),
                "status": result.get("status", ""),
            },
        )
        return result

    async def confirm_extraction(
        self,
        session_id: str,
        selected: Dict[str, List[str]] = None,
        selected_type_ids: List[str] = None,
        data: Dict[str, Any] = None,
        merge_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """Confirm and import extraction results into ontology.

        For HE-based sessions (stored in extraction.db): delegates to
        data.hyper_extract.ExtractService.confirm_extraction() which performs
        dual-channel write (Neo4j + Graphiti) with ProvenanceTracker recording.

        For database extraction sessions (stored in ontology.db): performs
        the classic type import with merge strategy (skip/overwrite/rename).
        This path preserves backward compatibility for sessions created by
        extract_from_database().

        Args:
            session_id: Extraction session ID.
            selected: Dict mapping type category to list of type names to import
                      (e.g. {"object_types": ["product"]}).
            selected_type_ids: Flat list of type names to import (backward compat).
            data: Override result_data for the session.
            merge_strategy: "skip" | "overwrite" | "rename".
        """
        _audit(
            "extraction_confirm_start",
            resource_id=session_id,
            details={"merge_strategy": merge_strategy},
        )

        # Convert selected_type_ids (flat list) to selected dict if needed
        if selected_type_ids and not selected:
            selected = {"object_types": selected_type_ids}

        # Check if this is a database extraction session (stored in ontology.db)
        db_session = self.ontology_service.get_extraction_session(session_id)
        if db_session and db_session.get("status") != "error":
            # Database extraction session — use classic import path
            result = self._confirm_database_session(
                session_id=session_id,
                session=db_session,
                selected=selected,
                data=data,
                merge_strategy=merge_strategy,
            )
        else:
            # HE-based session — delegate to new ExtractService
            result = await self.he_service.confirm_extraction(
                session_id=session_id,
                selected=selected,
                data=data,
                merge_strategy=merge_strategy,
            )

        _audit(
            "extraction_confirm_complete",
            resource_id=session_id,
            details={
                "status": result.get("status", ""),
                "imported": result.get("imported", {}),
            },
        )
        return result

    def _confirm_database_session(
        self,
        session_id: str,
        session: Dict[str, Any],
        selected: Dict[str, List[str]] = None,
        data: Dict[str, Any] = None,
        merge_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """Classic confirm path for database extraction sessions.

        Imports types from the session's result_data into the ontology
        using the specified merge strategy.
        """
        ontology_id = session.get("ontology_id", "")
        result_data = data or session.get("result_data", {})
        if not result_data:
            return {"status": "error", "message": "Session has no result_data"}

        # If data is provided, update the session's result_data first
        if data:
            self.ontology_service.update_extraction_session(
                session_id, {"result_data": data}
            )

        imported: Dict[str, int] = {}
        type_categories = [
            ("object_types", "create_object_type", "list_object_types"),
            ("link_types", "create_link_type", "list_link_types"),
            ("action_types", "create_action_type", "list_action_types"),
            ("process_types", "create_process_type", "list_process_types"),
            ("rule_types", "create_rule_type", "list_rule_types"),
            ("function_types", "create_function_type", "list_function_types"),
            ("indicator_types", "create_indicator_type", "list_indicator_types"),
        ]

        for cat_key, create_method_name, list_method_name in type_categories:
            items = result_data.get(cat_key, [])
            create_method = getattr(self.ontology_service, create_method_name, None)
            list_method = getattr(self.ontology_service, list_method_name, None)
            if not create_method or not list_method:
                imported[cat_key] = 0
                continue

            # Get existing items for conflict detection
            existing_result = list_method(ontology_id)
            existing_items = existing_result.get(cat_key, [])
            existing_names = {
                item.get("name")
                for item in existing_items
                if item.get("name")
            }

            # Filter by selected if provided
            selected_names = set()
            if selected and cat_key in selected:
                selected_names = set(selected[cat_key])

            count = 0
            for item in items:
                name = item.get("name", "")
                if not name:
                    continue
                # If selected filter is provided, skip unselected items
                if selected_names and name not in selected_names:
                    continue

                if name in existing_names:
                    if merge_strategy == "skip":
                        continue
                    elif merge_strategy == "overwrite":
                        # Find and update existing type
                        for existing_item in existing_items:
                            if existing_item.get("name") == name:
                                type_id = existing_item.get("type_id") or existing_item.get("id")
                                if type_id:
                                    # update_object_type takes (type_id, updates)
                                    update_method_name = f"update_{create_method_name.split('create_')[1]}"
                                    update_method = getattr(self.ontology_service, update_method_name, None)
                                    if update_method:
                                        try:
                                            update_method(type_id, item)
                                        except Exception as e:
                                            logger.warning("Failed to update %s '%s': %s", cat_key, name, e)
                                break
                        count += 1
                    elif merge_strategy == "rename":
                        renamed = dict(item)
                        renamed["name"] = f"{name}_imported"
                        try:
                            create_method(ontology_id, renamed)
                            count += 1
                        except Exception as e:
                            logger.warning("Failed to import renamed %s '%s': %s", cat_key, name, e)
                else:
                    # No conflict — create new
                    try:
                        create_method(ontology_id, item)
                        count += 1
                    except Exception as e:
                        logger.warning("Failed to import %s '%s': %s", cat_key, name, e)

            imported[cat_key] = count

        # Update session status to completed
        self.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "completed",
                "result_data": result_data,
            },
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "imported": imported,
            "channel_a_status": "success",
            "channel_b_status": "skipped",
        }

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get extraction session details.

        Tries the new ExtractService's session storage first (extraction.db),
        falls back to OntologyService's session storage for database extraction
        sessions that were created by extract_from_database().
        """
        # Try new ExtractService session storage first
        new_session = self.he_service.get_session(session_id)
        if new_session.get("status") == "ok":
            return new_session

        # Fall back to OntologyService session storage (for database extractions)
        session = self.ontology_service.get_extraction_session(session_id)
        if not session or session.get("status") == "error":
            return {"status": "error", "message": f"Session {session_id} not found"}
        return session

    # ------------------------------------------------------------------
    # Internal helpers (used by extract_from_database)
    # ------------------------------------------------------------------

    def _detect_conflicts(self, ontology_id: str, result: Dict) -> List[Dict]:
        """Detect conflicts between extraction results and existing types.

        Checks for:
        - Duplicate names across all type categories
        - Semantic similarity (Levenshtein distance < 3) for object_types
        """
        conflicts = []

        def _get_existing_names(list_method_name: str, result_key: str) -> set:
            method = getattr(self.ontology_service, list_method_name, None)
            if not method:
                return set()
            existing_result = method(ontology_id)
            return {
                item.get("name")
                for item in existing_result.get(result_key, [])
                if item.get("name")
            }

        type_categories = [
            ("object_types", "list_object_types", "object_types", "object_type"),
            ("link_types", "list_link_types", "link_types", "link_type"),
            ("action_types", "list_action_types", "action_types", "action_type"),
            ("rule_types", "list_rule_types", "rule_types", "rule_type"),
            ("process_types", "list_process_types", "process_types", "process_type"),
            ("function_types", "list_function_types", "function_types", "function_type"),
            ("indicator_types", "list_indicator_types", "indicator_types", "indicator_type"),
        ]

        for result_key, list_method, existing_key, conflict_type in type_categories:
            existing_names = _get_existing_names(list_method, existing_key)
            for item in result.get(result_key, []):
                name = item.get("name")
                if name and name in existing_names:
                    conflicts.append({
                        "type": conflict_type,
                        "name": name,
                        "conflict": "duplicate_name",
                        "existing": True,
                    })

        # Semantic similarity check for object_types
        existing_objects = _get_existing_names("list_object_types", "object_types")
        extracted_object_names = [
            ot.get("name") for ot in result.get("object_types", []) if ot.get("name")
        ]

        for ext_name in existing_objects:
            for new_name in extracted_object_names:
                if ext_name != new_name and self._levenshtein_distance(ext_name, new_name) < 3:
                    conflicts.append({
                        "type": "object_type",
                        "name": new_name,
                        "conflict": "similar_name",
                        "existing_name": ext_name,
                        "message": f"与已有类型 '{ext_name}' 名称相似",
                    })

        return conflicts

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Compute Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return ExtractionService._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        prev_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row

        return prev_row[-1]
