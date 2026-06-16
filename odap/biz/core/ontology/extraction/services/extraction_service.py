"""Extraction service for database and NL extraction.

Orchestrates extraction sessions and result merging into ontology type definitions.
Follows AGENTS.md Rule 2: returns Dict[str, Any], never raises HTTPException.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.ontology_api.services import OntologyService

logger = logging.getLogger(__name__)


class ExtractionService:
    """Orchestrates extraction sessions and result merging."""

    def __init__(self, db_path: str = None):
        self.ontology_service = OntologyService(db_path=db_path)

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

        Steps:
        1. Create extraction session record
        2. Run DatabaseSchemaExtractor to extract schema
        3. Detect conflicts with existing types
        4. Update session with results

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

    async def extract_from_nl(
        self,
        ontology_id: str,
        text: str,
        auto_search: bool = False,
    ) -> Dict[str, Any]:
        """Extract schema from natural language text and create extraction session.

        Steps:
        1. Create extraction session record
        2. Run SchemaLevelExtractor to extract types from NL
        3. Detect conflicts with existing types
        4. Update session with results

        Returns:
            Dict with keys: status, session_id, result, conflicts
        """
        # 1. Create session via OntologyService
        session_result = self.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="natural_language",
            input_data={"text": text[:500], "auto_search": auto_search},
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        # 2. Extract via LLM
        from odap.biz.core.ontology.extraction.services.schema_extractor import (
            SchemaLevelExtractor,
        )

        extractor = SchemaLevelExtractor()
        result = await extractor.extract_from_text(text, auto_search)

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

    def confirm_extraction(
        self,
        session_id: str,
        selected_type_ids: List[str] = None,
        merge_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """Confirm and import extraction results into ontology.

        Args:
            session_id: Extraction session ID
            selected_type_ids: Optional list of type names to import (empty = all)
            merge_strategy: One of 'skip', 'overwrite', 'rename'

        Returns:
            Dict with keys: status, imported (counts per type category)
        """
        session = self.ontology_service.get_extraction_session(session_id)
        if not session or session.get("status") == "error":
            return {"status": "error", "message": f"Session {session_id} not found"}

        result_data = session.get("result_data")
        if isinstance(result_data, str):
            result = json.loads(result_data)
        else:
            result = result_data or {}

        ontology_id = session["ontology_id"]

        imported = {
            "object_types": 0,
            "link_types": 0,
            "action_types": 0,
            "process_types": 0,
            "rule_types": 0,
            "function_types": 0,
            "indicator_types": 0,
        }

        # Import object types
        for ot in result.get("object_types", []):
            if selected_type_ids and ot["name"] not in selected_type_ids:
                continue
            # Check conflict
            existing = self._find_existing_type(ontology_id, ot["name"], "object")
            if existing:
                if merge_strategy == "skip":
                    continue
                elif merge_strategy == "overwrite":
                    self.ontology_service.update_object_type(existing["type_id"], ot)
                    imported["object_types"] += 1
                    continue
                elif merge_strategy == "rename":
                    ot["name"] = f"{ot['name']}_imported"
                    ot["display_name"] = f"{ot.get('display_name', ot['name'])} (导入)"
            self.ontology_service.create_object_type(ontology_id, ot)
            imported["object_types"] += 1

        # Import link types
        for lt in result.get("link_types", []):
            if selected_type_ids and lt["name"] not in selected_type_ids:
                continue
            self.ontology_service.create_link_type(ontology_id, lt)
            imported["link_types"] += 1

        # Import action types
        for at in result.get("action_types", []):
            if selected_type_ids and at.get("name") not in selected_type_ids:
                continue
            self.ontology_service.create_action_type(ontology_id, at)
            imported["action_types"] += 1

        # Import process types
        for pt in result.get("process_types", []):
            if selected_type_ids and pt.get("name") not in selected_type_ids:
                continue
            self.ontology_service.create_process_type(ontology_id, pt)
            imported["process_types"] += 1

        # Import rule types
        for rt in result.get("rule_types", []):
            if selected_type_ids and rt.get("name") not in selected_type_ids:
                continue
            self.ontology_service.create_rule_type(ontology_id, rt)
            imported["rule_types"] += 1

        # Import function types
        for ft in result.get("function_types", []):
            if selected_type_ids and ft.get("name") not in selected_type_ids:
                continue
            self.ontology_service.create_function_type(ontology_id, ft)
            imported["function_types"] += 1

        # Import indicator types
        for it in result.get("indicator_types", []):
            if selected_type_ids and it.get("name") not in selected_type_ids:
                continue
            self.ontology_service.create_indicator_type(ontology_id, it)
            imported["indicator_types"] += 1

        # Update session status
        self.ontology_service.update_extraction_session(session_id, {"status": "completed"})

        return {"status": "ok", "imported": imported}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get extraction session details."""
        session = self.ontology_service.get_extraction_session(session_id)
        if not session or session.get("status") == "error":
            return {"status": "error", "message": f"Session {session_id} not found"}
        return session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_conflicts(self, ontology_id: str, result: Dict) -> List[Dict]:
        """Detect conflicts between extraction results and existing types.

        Checks for:
        - Duplicate names across all type categories
        - Semantic similarity (Levenshtein distance < 3) for object_types
        """
        conflicts = []

        # ── Helper: collect existing names for a type category ──────
        def _get_existing_names(list_method_name: str, result_key: str) -> set:
            """Call OntologyService list method and return a set of names."""
            method = getattr(self.ontology_service, list_method_name, None)
            if not method:
                return set()
            existing_result = method(ontology_id)
            return {
                item.get("name")
                for item in existing_result.get(result_key, [])
                if item.get("name")
            }

        # ── Check each type category for duplicate names ───────────
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

        # ── Semantic similarity check for object_types ─────────────
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

    def _find_existing_type(
        self, ontology_id: str, name: str, type_category: str
    ) -> Optional[Dict]:
        """Find existing type by name in the given category."""
        if type_category == "object":
            result = self.ontology_service.list_object_types(ontology_id)
            for ot in result.get("object_types", []):
                if ot.get("name") == name:
                    return ot
        return None
