"""Extraction service for database and NL extraction.

Orchestrates extraction sessions and result merging into ontology type definitions.
Follows AGENTS.md Rule 2: returns Dict[str, Any], never raises HTTPException.
"""

import json
import logging
import os
import shutil
import tempfile
import uuid
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
        template_id: str = None,
        method: str = None,
    ) -> Dict[str, Any]:
        """Extract schema from natural language text and create extraction session.

        Steps:
        1. Validate input
        2. Create extraction session record
        3. Resolve template via 3-level fallback
        4. Extract via HEAdapter (or fallback to SchemaLevelExtractor)
        5. Map results via OntologyMapper
        6. Detect conflicts with existing types
        7. Update session with results

        Returns:
            Dict with keys: status, session_id, result, conflicts, template_used
        """
        if not text or not text.strip():
            return {"status": "error", "message": "Text cannot be empty"}

        _audit("extraction_nl_start", resource_id=ontology_id, details={"text_length": len(text), "auto_search": auto_search, "template_id": template_id, "method": method})

        # 1. Create session via OntologyService
        session_result = self.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="natural_language",
            input_data={"text": text[:500], "auto_search": auto_search},
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        # 2. Try HE pipeline
        from odap.biz.core.ontology.extraction.impl.he_adapter import HEAdapter
        from odap.biz.core.ontology.extraction.impl.ontology_mapper import OntologyMapper
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        he_adapter = HEAdapter()
        template_used = None
        provenance_summary = None

        if he_adapter.available:
            try:
                # 3. Resolve template via 3-level fallback
                template_generator = TemplateGenerator()
                template_config = None

                if template_id:
                    template_config = {"name": template_id}
                    template_used = template_id
                else:
                    template_config = template_generator.generate_from_ontology(ontology_id)
                    if template_config:
                        template_used = template_config.get("name", "ontology_generated")
                    else:
                        domain_hint = template_generator._infer_domain(text) if hasattr(template_generator, '_infer_domain') else "general"
                        template_config = template_generator.select_preset(domain_hint)
                        if template_config:
                            template_used = template_config.get("name", f"preset_{domain_hint}")
                        elif auto_search:
                            template_config = template_generator.generate_with_web_search(text)
                            if template_config:
                                template_used = template_config.get("name", "web_search_generated")

                if method:
                    template_config = template_config or {}
                    template_config["method"] = method

                # 4. Extract via HE
                ka_result = he_adapter.extract_from_text(text, template_config or {})

                # 5. Map results via OntologyMapper
                mapper = OntologyMapper()
                schema_result = mapper.map_to_schema(ka_result)
                instance_result = mapper.map_to_instances(ka_result)

                result = {
                    **schema_result,
                    "entities": instance_result.get("entities", []),
                    "relations": instance_result.get("relations", []),
                }

                provenance_summary = {
                    "total_entities": len(instance_result.get("entities", [])),
                    "total_relations": len(instance_result.get("relations", [])),
                    "extraction_method": method or "auto",
                    "template_used": template_used,
                }

            except TimeoutError:
                self.ontology_service.update_extraction_session(
                    session_id,
                    {"status": "failed", "result_data": {"error": "LLM timeout"}},
                )
                return {"status": "error", "message": "Extraction timed out, please try again"}
            except RuntimeError as e:
                if "Hyper-Extract" in str(e):
                    logger.warning("HE unavailable, falling back to SchemaLevelExtractor: %s", e)
                    result = await self._extract_via_schema_level(text, auto_search)
                    template_used = "schema_level_fallback"
                else:
                    raise
        else:
            # HE not available, fallback
            result = await self._extract_via_schema_level(text, auto_search)
            template_used = "schema_level_fallback"

        if result.get("status") == "error":
            self.ontology_service.update_extraction_session(
                session_id,
                {"status": "failed", "result_data": result},
            )
            return result

        # 6. Detect conflicts with existing types
        conflicts = self._detect_conflicts(ontology_id, result)

        # 7. Update session
        self.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "reviewing",
                "result_data": result,
                "conflicts": conflicts,
            },
        )

        _audit("extraction_nl_complete", resource_id=session_id, details={"ontology_id": ontology_id, "session_id": session_id, "template_used": template_used, "conflict_count": len(conflicts)})

        return {
            "status": "ok",
            "session_id": session_id,
            "result": result,
            "conflicts": conflicts,
            "template_used": template_used,
            "provenance_summary": provenance_summary,
        }

    async def extract_from_document(
        self,
        ontology_id: str,
        file_path: str,
        template_id: str = None,
        method: str = None,
    ) -> Dict[str, Any]:
        """Extract schema from a document file and create extraction session.

        Steps:
        1. Parse document via DocumentParser
        2. Chunk text via DocumentParser.chunk_text()
        3. Create extraction session (type="document")
        4. For each chunk, extract via HEAdapter (or fallback to SchemaLevelExtractor)
        5. Merge all chunk results via HEAdapter.merge_results()
        6. Map merged results via OntologyMapper
        7. Record provenance for each chunk via ProvenanceTracker
        8. Detect conflicts
        9. Update session

        Failed chunks are skipped and marked for retry (EC-006).

        Returns:
            Dict with keys: status, session_id, result, conflicts, template_used, provenance_summary
        """
        from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
        from odap.biz.core.ontology.extraction.impl.he_adapter import HEAdapter
        from odap.biz.core.ontology.extraction.impl.ontology_mapper import OntologyMapper
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        _audit("extraction_doc_start", resource_id=ontology_id, details={"file_path": os.path.basename(file_path), "template_id": template_id, "method": method})

        # 1. Parse document
        parser = DocumentParser()
        try:
            full_text = parser.parse(file_path)
        except (FileNotFoundError, ValueError) as e:
            return {"status": "error", "message": str(e)}

        if not full_text or not full_text.strip():
            return {"status": "error", "message": "Document produced no extractable text"}

        # 2. Chunk text
        chunks = parser.chunk_text(full_text)
        source_doc_id = str(uuid.uuid4())

        # 3. Create session
        session_result = self.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="document",
            input_data={
                "file_path": os.path.basename(file_path),
                "source_doc_id": source_doc_id,
                "total_chunks": len(chunks),
            },
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        # 4. Resolve template via 3-level fallback
        he_adapter = HEAdapter()
        template_used = None
        template_config = None

        if he_adapter.available:
            template_generator = TemplateGenerator()
            if template_id:
                template_config = {"name": template_id}
                template_used = template_id
            else:
                template_config = template_generator.generate_from_ontology(ontology_id)
                if template_config:
                    template_used = template_config.get("name", "ontology_generated")
                else:
                    domain_hint = template_generator._infer_domain(full_text[:500]) if hasattr(template_generator, '_infer_domain') else "general"
                    template_config = template_generator.select_preset(domain_hint)
                    if template_config:
                        template_used = template_config.get("name", f"preset_{domain_hint}")

            if method:
                template_config = template_config or {}
                template_config["method"] = method

        # 5. Extract from each chunk
        chunk_results: List[Dict[str, Any]] = []
        failed_chunks: List[Dict[str, Any]] = []
        provenance_tracker = ProvenanceTracker()

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{source_doc_id}_chunk_{idx}"
            try:
                if he_adapter.available:
                    chunk_result = he_adapter.extract_from_text(chunk, template_config or {})
                else:
                    chunk_result = await self._extract_via_schema_level(chunk, auto_search=False)
                    if chunk_result.get("status") == "error":
                        raise RuntimeError(chunk_result.get("message", "SchemaLevelExtractor failed"))

                chunk_results.append(chunk_result)

                # 7. Record provenance for each entity in the chunk
                for node in chunk_result.get("nodes", []):
                    entity_id = node.get("id", str(uuid.uuid4()))
                    provenance_tracker.record_extraction(
                        entity_id=entity_id,
                        source_doc_id=source_doc_id,
                        chunk_id=chunk_id,
                        fragment_id=f"{chunk_id}_frag_0",
                        method=method or ("he" if he_adapter.available else "schema_level"),
                        template_version=template_used or "",
                    )

            except Exception as e:
                logger.warning("Chunk %d extraction failed, marking for retry: %s", idx, e)
                failed_chunks.append({
                    "chunk_index": idx,
                    "chunk_id": chunk_id,
                    "error": str(e),
                    "retry_eligible": True,
                })

        if not chunk_results:
            self.ontology_service.update_extraction_session(
                session_id,
                {
                    "status": "failed",
                    "result_data": {"error": "All chunks failed", "failed_chunks": failed_chunks},
                },
            )
            return {
                "status": "error",
                "message": "All document chunks failed extraction",
                "failed_chunks": failed_chunks,
            }

        # 5b. Merge all chunk results
        if he_adapter.available and len(chunk_results) > 1:
            merged_ka = he_adapter.merge_results(chunk_results)
        elif len(chunk_results) == 1:
            merged_ka = chunk_results[0]
        else:
            merged_ka = {"nodes": [], "edges": []}
            for cr in chunk_results:
                merged_ka.setdefault("nodes", []).extend(cr.get("nodes", []))
                merged_ka.setdefault("edges", []).extend(cr.get("edges", []))

        # 6. Map results via OntologyMapper
        mapper = OntologyMapper()
        schema_result = mapper.map_to_schema(merged_ka)
        instance_result = mapper.map_to_instances(merged_ka)

        result = {
            **schema_result,
            "entities": instance_result.get("entities", []),
            "relations": instance_result.get("relations", []),
        }

        provenance_summary = {
            "source_doc_id": source_doc_id,
            "total_chunks": len(chunks),
            "successful_chunks": len(chunk_results),
            "failed_chunks": len(failed_chunks),
            "total_entities": len(instance_result.get("entities", [])),
            "total_relations": len(instance_result.get("relations", [])),
            "extraction_method": method or ("he" if he_adapter.available else "schema_level"),
            "template_used": template_used,
            "failed_chunk_details": failed_chunks,
        }

        if result.get("status") == "error":
            self.ontology_service.update_extraction_session(
                session_id,
                {"status": "failed", "result_data": result},
            )
            return result

        # 8. Detect conflicts
        conflicts = self._detect_conflicts(ontology_id, result)

        # 9. Update session
        self.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "reviewing",
                "result_data": result,
                "conflicts": conflicts,
            },
        )

        _audit("extraction_doc_complete", resource_id=session_id, details={"ontology_id": ontology_id, "session_id": session_id, "template_used": template_used, "conflict_count": len(conflicts), "source_doc_id": source_doc_id})

        return {
            "status": "ok",
            "session_id": session_id,
            "result": result,
            "conflicts": conflicts,
            "template_used": template_used,
            "provenance_summary": provenance_summary,
        }

    async def extract_from_knowledge_base(
        self,
        ontology_id: str,
        kb_id: str,
        template_id: str = None,
        method: str = None,
        document_ids: List[str] = None,
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """Extract schema from a knowledge base and create extraction session.

        Steps:
        1. Create extraction session (type="knowledge_base")
        2. Read knowledge base document list from KB service
        3. If document_ids provided, filter to only those documents
        4. For each document:
           a. Get document content (from KB storage or file path)
           b. Parse via DocumentParser if file path available
           c. Extract via HEAdapter (or fallback to SchemaLevelExtractor)
           d. Merge results incrementally
           e. Record provenance for each document's extraction
        5. Empty knowledge base returns error (EC-004)
        6. Empty documents are skipped (EC-010)
        7. Batch processing: process batch_size documents at a time (EC-013)
        8. Detect conflicts
        9. Update session

        Returns:
            Dict with keys: status, session_id, result, conflicts, template_used, provenance_summary
        """
        from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
        from odap.biz.core.ontology.extraction.impl.he_adapter import HEAdapter
        from odap.biz.core.ontology.extraction.impl.ontology_mapper import OntologyMapper
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        _audit("extraction_kb_start", resource_id=ontology_id, details={"kb_id": kb_id, "template_id": template_id, "method": method, "document_ids": document_ids, "batch_size": batch_size})

        try:
            from odap.biz.data.knowledge_base.services import get_kb_service
            kb_service = get_kb_service()
        except Exception:
            kb_service = None

        if not kb_service:
            return {"status": "error", "message": "Knowledge base service unavailable (EC-004)"}

        kb = kb_service.get_knowledge_base(kb_id)
        if not kb or kb.get("status") == "error":
            return {"status": "error", "message": f"Knowledge base '{kb_id}' not found (EC-004)"}

        all_docs = kb_service.list_documents(kb_id)
        if not all_docs:
            return {"status": "error", "message": f"Knowledge base '{kb_id}' is empty (EC-004)"}

        if document_ids:
            doc_id_set = set(document_ids)
            all_docs = [d for d in all_docs if d.get("doc_id") in doc_id_set]
            if not all_docs:
                return {"status": "error", "message": "None of the specified document_ids found in knowledge base (EC-004)"}

        session_result = self.ontology_service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type="knowledge_base",
            input_data={
                "kb_id": kb_id,
                "document_ids": document_ids,
                "total_documents": len(all_docs),
            },
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        he_adapter = HEAdapter()
        template_used = None
        template_config = None

        if he_adapter.available:
            template_generator = TemplateGenerator()
            if template_id:
                template_config = {"name": template_id}
                template_used = template_id
            else:
                template_config = template_generator.generate_from_ontology(ontology_id)
                if template_config:
                    template_used = template_config.get("name", "ontology_generated")
                else:
                    kb_text_sample = " ".join(
                        (d.get("content", "") or "")[:200] for d in all_docs[:3]
                    )
                    domain_hint = (
                        template_generator._infer_domain(kb_text_sample)
                        if hasattr(template_generator, "_infer_domain")
                        else "general"
                    )
                    template_config = template_generator.select_preset(domain_hint)
                    if template_config:
                        template_used = template_config.get("name", f"preset_{domain_hint}")

            if method:
                template_config = template_config or {}
                template_config["method"] = method

        provenance_tracker = ProvenanceTracker()
        parser = DocumentParser()
        all_chunk_results: List[Dict[str, Any]] = []
        failed_docs: List[Dict[str, Any]] = []
        skipped_docs: List[Dict[str, Any]] = []
        doc_provenance: List[Dict[str, Any]] = []

        for batch_start in range(0, len(all_docs), batch_size):
            batch = all_docs[batch_start : batch_start + batch_size]

            for doc in batch:
                doc_id = doc.get("doc_id", str(uuid.uuid4()))
                content = doc.get("content", "") or ""
                file_path = doc.get("file_path") or doc.get("source_path")

                if file_path and os.path.exists(file_path):
                    try:
                        content = parser.parse(file_path)
                    except (FileNotFoundError, ValueError) as e:
                        logger.warning("Document %s parse failed: %s", doc_id, e)
                        failed_docs.append({
                            "doc_id": doc_id,
                            "title": doc.get("title", ""),
                            "error": str(e),
                        })
                        continue

                if not content or not content.strip():
                    skipped_docs.append({
                        "doc_id": doc_id,
                        "title": doc.get("title", ""),
                        "reason": "empty content (EC-010)",
                    })
                    continue

                chunks = parser.chunk_text(content)

                for idx, chunk in enumerate(chunks):
                    chunk_id = f"{doc_id}_chunk_{idx}"
                    try:
                        if he_adapter.available:
                            chunk_result = he_adapter.extract_from_text(
                                chunk, template_config or {}
                            )
                        else:
                            chunk_result = await self._extract_via_schema_level(
                                chunk, auto_search=False
                            )
                            if chunk_result.get("status") == "error":
                                raise RuntimeError(
                                    chunk_result.get("message", "SchemaLevelExtractor failed")
                                )

                        all_chunk_results.append(chunk_result)

                        for node in chunk_result.get("nodes", []):
                            entity_id = node.get("id", str(uuid.uuid4()))
                            provenance_tracker.record_extraction(
                                entity_id=entity_id,
                                source_doc_id=doc_id,
                                chunk_id=chunk_id,
                                fragment_id=f"{chunk_id}_frag_0",
                                method=method or ("he" if he_adapter.available else "schema_level"),
                                template_version=template_used or "",
                            )

                    except Exception as e:
                        logger.warning(
                            "Doc %s chunk %d extraction failed: %s", doc_id, idx, e
                        )
                        failed_docs.append({
                            "doc_id": doc_id,
                            "chunk_index": idx,
                            "error": str(e),
                        })

                doc_provenance.append({
                    "doc_id": doc_id,
                    "title": doc.get("title", ""),
                    "chunks": len(chunks),
                    "status": "processed",
                })

        if not all_chunk_results:
            self.ontology_service.update_extraction_session(
                session_id,
                {
                    "status": "failed",
                    "result_data": {
                        "error": "No extractable content found",
                        "failed_docs": failed_docs,
                        "skipped_docs": skipped_docs,
                    },
                },
            )
            return {
                "status": "error",
                "message": "No extractable content found in knowledge base documents",
                "failed_docs": failed_docs,
                "skipped_docs": skipped_docs,
            }

        if he_adapter.available and len(all_chunk_results) > 1:
            merged_ka = he_adapter.merge_results(all_chunk_results)
        elif len(all_chunk_results) == 1:
            merged_ka = all_chunk_results[0]
        else:
            merged_ka = {"nodes": [], "edges": []}
            for cr in all_chunk_results:
                merged_ka.setdefault("nodes", []).extend(cr.get("nodes", []))
                merged_ka.setdefault("edges", []).extend(cr.get("edges", []))

        mapper = OntologyMapper()
        schema_result = mapper.map_to_schema(merged_ka)
        instance_result = mapper.map_to_instances(merged_ka)

        result = {
            **schema_result,
            "entities": instance_result.get("entities", []),
            "relations": instance_result.get("relations", []),
        }

        provenance_summary = {
            "kb_id": kb_id,
            "total_documents": len(all_docs),
            "processed_documents": len(doc_provenance),
            "skipped_documents": len(skipped_docs),
            "failed_documents": len(failed_docs),
            "total_chunks": len(all_chunk_results),
            "total_entities": len(instance_result.get("entities", [])),
            "total_relations": len(instance_result.get("relations", [])),
            "extraction_method": method or ("he" if he_adapter.available else "schema_level"),
            "template_used": template_used,
            "document_details": doc_provenance,
            "skipped_details": skipped_docs,
            "failed_details": failed_docs,
        }

        if result.get("status") == "error":
            self.ontology_service.update_extraction_session(
                session_id,
                {"status": "failed", "result_data": result},
            )
            return result

        conflicts = self._detect_conflicts(ontology_id, result)

        self.ontology_service.update_extraction_session(
            session_id,
            {
                "status": "reviewing",
                "result_data": result,
                "conflicts": conflicts,
            },
        )

        _audit("extraction_kb_complete", resource_id=session_id, details={"ontology_id": ontology_id, "session_id": session_id, "kb_id": kb_id, "template_used": template_used, "conflict_count": len(conflicts)})

        return {
            "status": "ok",
            "session_id": session_id,
            "result": result,
            "conflicts": conflicts,
            "template_used": template_used,
            "provenance_summary": provenance_summary,
        }

    async def _extract_via_schema_level(
        self, text: str, auto_search: bool,
    ) -> Dict[str, Any]:
        """Fallback extraction using SchemaLevelExtractor when HE is unavailable."""
        from odap.biz.core.ontology.extraction.services.schema_extractor import (
            SchemaLevelExtractor,
        )

        extractor = SchemaLevelExtractor()
        return await extractor.extract_from_text(text, auto_search)

    async def confirm_extraction(
        self,
        session_id: str,
        selected_type_ids: List[str] = None,
        merge_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """Confirm and import extraction results into ontology with dual-channel write.

        Channel A (primary): Write entities with full properties to Neo4j via
        GraphWriteProxy. Skipped if GraphWriteProxy is unavailable.

        Channel B (secondary): Write structured summary to Graphiti for
        dual-temporal indexing via GraphManager. Failure does NOT rollback
        Channel A (EC-011).

        Args:
            session_id: Extraction session ID
            selected_type_ids: Optional list of type names to import (empty = all)
            merge_strategy: One of 'skip', 'overwrite', 'rename'

        Returns:
            Dict with keys: status, imported, channel_a_status, channel_b_status
        """
        session = self.ontology_service.get_extraction_session(session_id)
        if not session or session.get("status") == "error":
            return {"status": "error", "message": f"Session {session_id} not found"}

        _audit("extraction_confirm", resource_id=session_id, details={"session_id": session_id, "selected_type_ids": selected_type_ids, "merge_strategy": merge_strategy})

        result_data = session.get("result_data")
        if isinstance(result_data, str):
            try:
                result = json.loads(result_data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Failed to parse result_data for session %s: %s", session_id, e)
                return {"status": "error", "message": f"Malformed result data in session {session_id}"}
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

        imported_items: List[Dict[str, Any]] = []

        type_import_specs = [
            ("object_types", "object", "create_object_type", "update_object_type"),
            ("link_types", "link", "create_link_type", "update_link_type"),
            ("action_types", "action", "create_action_type", "update_action_type"),
            ("process_types", "process", "create_process_type", "update_process_type"),
            ("rule_types", "rule", "create_rule_type", "update_rule_type"),
            ("function_types", "function", "create_function_type", "update_function_type"),
            ("indicator_types", "indicator", "create_indicator_type", "update_indicator_type"),
        ]

        for result_key, category, create_method, update_method in type_import_specs:
            for item in result.get(result_key, []):
                if selected_type_ids and item.get("name") not in selected_type_ids:
                    continue
                existing = self._find_existing_type(ontology_id, item["name"], category)
                if existing:
                    if merge_strategy == "skip":
                        continue
                    elif merge_strategy == "overwrite":
                        getattr(self.ontology_service, update_method)(existing["type_id"], item)
                        imported[result_key] += 1
                        imported_items.append({"category": category, "name": item.get("name", ""), "item": dict(item)})
                        continue
                    elif merge_strategy == "rename":
                        item["name"] = f"{item['name']}_imported"
                        item["display_name"] = f"{item.get('display_name', item['name'])} (导入)"
                getattr(self.ontology_service, create_method)(ontology_id, item)
                imported[result_key] += 1
                imported_items.append({"category": category, "name": item.get("name", ""), "item": dict(item)})

        # ── Channel A: Write entities to Neo4j via GraphWriteProxy ──
        channel_a_status = "skipped"
        try:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy

            write_proxy = get_graph_write_proxy()

            for entry in imported_items:
                category = entry["category"]
                item_name = entry["name"]
                item_data = entry["item"]
                entity_id = f"{ontology_id}_{category}_{item_name}"
                properties = {
                    "name": item_name,
                    "display_name": item_data.get("display_name", ""),
                    "description": item_data.get("description", ""),
                    "ontology_id": ontology_id,
                    "session_id": session_id,
                    "source": "extraction_confirm",
                    "type_category": category,
                }
                write_result = write_proxy.add_entity(
                    entity_id=entity_id,
                    entity_type=category,
                    properties=properties,
                )
                if write_result.get("status") != "success":
                    logger.warning(
                        "Channel A: failed to write entity %s: %s",
                        item_name,
                        write_result.get("message", ""),
                    )
            channel_a_status = "success"
        except ImportError:
            logger.warning("GraphWriteProxy not available, skipping Channel A")
        except Exception as e:
            logger.error("Channel A write failed: %s", e)
            channel_a_status = "failed"

        # ── Channel B: Write structured summary to Graphiti ──
        channel_b_status = "skipped"
        try:
            from odap.infra.graph.graph_service import GraphManager

            graph_manager = GraphManager.get_instance()

            structured_summary = json.dumps(imported, ensure_ascii=False)
            await graph_manager.add_episode(
                name=f"extraction_confirm:{ontology_id}",
                content=structured_summary,
                source_description=f"ontology:{ontology_id}",
            )
            channel_b_status = "success"
        except ImportError:
            logger.warning("GraphManager not available, skipping Channel B")
        except Exception as e:
            logger.error("Channel B write failed (EC-011): %s", e)
            channel_b_status = "failed"

        self.ontology_service.update_extraction_session(session_id, {
            "status": "completed",
            "channel_b_status": channel_b_status,
        })

        return {
            "status": "ok",
            "imported": imported,
            "channel_a_status": channel_a_status,
            "channel_b_status": channel_b_status,
        }

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
        """Find existing type by name in the given category.

        Supports all 7 type categories: object, link, action, process,
        rule, function, indicator.
        """
        category_map = {
            "object": ("list_object_types", "object_types"),
            "link": ("list_link_types", "link_types"),
            "action": ("list_action_types", "action_types"),
            "process": ("list_process_types", "process_types"),
            "rule": ("list_rule_types", "rule_types"),
            "function": ("list_function_types", "function_types"),
            "indicator": ("list_indicator_types", "indicator_types"),
        }
        entry = category_map.get(type_category)
        if not entry:
            return None
        list_method_name, result_key = entry
        method = getattr(self.ontology_service, list_method_name, None)
        if not method:
            return None
        result = method(ontology_id)
        for item in result.get(result_key, []):
            if item.get("name") == name:
                return item
        return None
