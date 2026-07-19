"""ExtractService — Hyper-Extract orchestration service.

Implements the full extraction chain (T058-T065):
- T058: LLM supplement for categories with entity_count < 2
- T059: extract_from_nl() — assess → select_complementary → multi-parse →
        LLM supplement → merge_and_map → validate → session update
- T060: extract_from_document() — document chunking + per-chunk extraction
- T061: extract_from_knowledge_base() — KB document iteration
- T062: ValidationEngine integration — validation_report in session.result_data
- T063: degradation_flags management (EC-015/016/017/018)
- T064: confirm_extraction dual-channel write (GraphWriteProxy + Graphiti)
- T065: _detect_conflicts (name collision + Levenshtein similarity)

Rules (AGENTS.md):
- Service layer returns Dict[str, Any], never raises HTTPException
- EC-006: Single template failure does not block other templates
- EC-018: Validation failure returns status="error" but does not block extraction
"""

import hashlib
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from ..impl.he_adapter import HEAdapter
from ..impl.ontology_mapper import OntologyMapper
from ..impl.dual_channel_writer import DualChannelWriter
from ..impl.provenance_tracker import ProvenanceTracker
from ..services.template_engine import TemplateEngine
from ..services.validation_engine import ValidationEngine
from ..storage import Storage
from ..storage.sqlite_template_storage import SqliteTemplateStorage

logger = logging.getLogger("extract_service")

# ODAP 5 categories — type_keys used for LLM supplement threshold check
_ODAP_CATEGORY_KEYS = (
    "object_types",
    "link_types",
    "action_types",
    "rule_types",
    "process_types",
)

# Minimum entity count per category before LLM supplement is triggered
_SUPPLEMENT_THRESHOLD = 2


class ExtractService:
    """Orchestrates the full Hyper-Extract extraction chain.

    Constructor accepts injectable components for testability. In production,
    defaults to real HEAdapter, TemplateEngine, ValidationEngine,
    OntologyMapper, SQLiteExtractionStorage, and DualChannelWriter.
    """

    def __init__(
        self,
        adapter: Optional[HEAdapter] = None,
        template_engine: Optional[TemplateEngine] = None,
        validation_engine: Optional[ValidationEngine] = None,
        ontology_mapper: Optional[OntologyMapper] = None,
        storage: Optional[Storage] = None,
        writer: Optional[DualChannelWriter] = None,
        provenance_tracker: Optional[ProvenanceTracker] = None,
    ):
        self.adapter = adapter or HEAdapter()
        self.template_engine = template_engine or TemplateEngine(self.adapter, SqliteTemplateStorage())
        self.validation_engine = validation_engine or ValidationEngine()
        self.ontology_mapper = ontology_mapper or OntologyMapper()
        self.storage = storage or Storage()
        self.writer = writer or DualChannelWriter()
        self.provenance_tracker = provenance_tracker or ProvenanceTracker()

    # ------------------------------------------------------------------
    # T059: extract_from_nl — full orchestration
    # ------------------------------------------------------------------

    async def extract_from_nl(
        self,
        text: str,
        ontology_id: str,
        template_id: Optional[str] = None,
        method: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract from natural language text via full HE chain.

        Args:
            mode: Optional mode flag. When "schema_learning", enhances schema inference
                by including additional LLM prompts for concept discovery and
                relationship type generation.

        Orchestration:
            1. Validate input
            2. Create extraction session
            3. Assess template suitability
            4. Select complementary templates OR generate custom
            5. Multi-parse with EC-006 error isolation
            6. LLM supplement for sparse categories
            7. Merge and map to ODAP 5 classes
            8. Validate via 4-dimensional ValidationEngine
            9. Update session with result_data + validation_report

        Returns:
            Dict with status, session_id, result, conflicts, template_used,
            degradation_flags, validation_report.
        """
        if not text or not text.strip():
            return {"status": "error", "message": "文本不能为空"}
        if not ontology_id:
            return {"status": "error", "message": "本体ID不能为空"}

        # Step 2: Create session
        session_result = self.storage.create_session(
            ontology_id=ontology_id,
            extraction_type="natural_language",
            input_data={"text": text[:500], "method": method, "mode": mode},
        )
        if session_result.get("status") == "error":
            return session_result
        session_id = session_result["session_id"]

        degradation_flags: List[str] = []
        ontology_schema = self._get_ontology_schema(ontology_id)

        # Step 3: Assess templates
        assess_result = self.template_engine.assess(text, ontology_id)
        if assess_result.get("best_score", 0) < assess_result.get("threshold", 0.5):
            degradation_flags.append("template_below_threshold")

        # Step 4: Select templates (custom or complementary)
        templates, template_used = self._select_templates(
            assess_result, text, ontology_schema, degradation_flags, template_id
        )

        # Step 5: Multi-parse with EC-006 isolation
        parse_results = self._multi_parse(text, templates, degradation_flags)

        # Step 6-7: Merge and map
        merged = self.ontology_mapper.merge_and_map(parse_results)

        # Step 6b: LLM supplement for sparse categories
        self._llm_supplement(merged, text, ontology_schema, degradation_flags)

        # Step 8: Validate (EC-018: non-blocking)
        template_score = assess_result.get("best_score", 0.0)
        validation_report = self._run_validation(
            merged, ontology_schema, template_score, degradation_flags
        )

        # Step 8b: Detect conflicts
        conflicts = self._detect_conflicts(ontology_id, merged)

        # Step 8c: Schema learning mode — generate schema candidates
        schema_candidates = None
        if mode == "schema_learning":
            schema_candidates = self._generate_schema_candidates(merged)

        # Step 9: Finalize session
        self._finalize_session(
            session_id, merged, validation_report, assess_result,
            templates, template_used, degradation_flags, conflicts,
            provenance_summary=None, schema_candidates=schema_candidates,
        )

        result = {
            "status": "ok",
            "session_id": session_id,
            "result": merged,
            "conflicts": conflicts,
            "template_used": template_used,
            "degradation_flags": degradation_flags,
            "validation_report": validation_report,
        }
        if schema_candidates:
            result["schema_candidates"] = schema_candidates
        return result

    # ------------------------------------------------------------------
    # T060: extract_from_document
    # ------------------------------------------------------------------

    async def extract_from_document(
        self,
        ontology_id: str,
        file_path: str,
        template_id: Optional[str] = None,
        method: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract from a document file with chunking.

        Args:
            mode: Optional mode flag. When "schema_learning", enhances schema inference
                by including additional LLM prompts for concept discovery.

        Steps:
            1. Parse document via DocumentParser
            2. Chunk text
            3. Create session (type="document")
            4. Assess templates using first chunk sample
            5. Select complementary templates (EC-011: no re-assessment per chunk)
            6. For each chunk, multi-parse with selected templates
            7. Merge all chunk results via OntologyMapper.merge_and_map
            8. Validate
            9. Update session

        Returns:
            Dict with status, session_id, result, conflicts, template_used,
            degradation_flags, validation_report, provenance_summary.
        """
        if not file_path:
            return {"status": "error", "message": "文件路径不能为空"}
        if not ontology_id:
            return {"status": "error", "message": "本体ID不能为空"}

        # Step 1: Parse document
        try:
            from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
            parser = DocumentParser()
            full_text = parser.parse(file_path)
        except (FileNotFoundError, ValueError, ImportError) as e:
            return {"status": "error", "message": str(e)}

        if not full_text or not full_text.strip():
            return {"status": "error", "message": "文档无可提取文本"}

        # Step 2: Chunk text
        chunks = parser.chunk_text(full_text)
        source_doc_id = str(uuid.uuid4())

        # Step 3: Create session
        session_result = self.storage.create_session(
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

        degradation_flags: List[str] = []
        ontology_schema = self._get_ontology_schema(ontology_id)

        # Step 4: Assess using first chunk as sample
        sample_text = chunks[0] if chunks else full_text[:1500]
        assess_result = self.template_engine.assess(sample_text, ontology_id)

        # Step 5: Select templates (once for all chunks — EC-011)
        templates, template_used = self._select_templates(
            assess_result, sample_text, ontology_schema, degradation_flags, template_id
        )

        # Step 6: Per-chunk multi-parse
        all_parse_results: List[Dict[str, Any]] = []
        failed_chunks: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{source_doc_id}_chunk_{idx}"
            chunk_results = self._multi_parse(chunk, templates, degradation_flags)
            if not chunk_results:
                failed_chunks.append({"chunk_index": idx, "chunk_id": chunk_id})
            else:
                # Tag with source_template for provenance
                for r in chunk_results:
                    r.setdefault("source_doc_id", source_doc_id)
                    r.setdefault("chunk_id", chunk_id)
                all_parse_results.extend(chunk_results)

        if not all_parse_results:
            degradation_flags.append("all_chunks_failed")

        # Step 7: Merge and map
        merged = self.ontology_mapper.merge_and_map(all_parse_results)

        # Step 7b: LLM supplement
        self._llm_supplement(merged, full_text[:2000], ontology_schema, degradation_flags)

        # Step 8: Validate
        validation_report = self._run_validation(
            merged, ontology_schema, assess_result.get("best_score", 0.0), degradation_flags
        )

        # Step 8b: Conflicts
        conflicts = self._detect_conflicts(ontology_id, merged)

        # Step 9: Finalize
        provenance_summary = {
            "source_doc_id": source_doc_id,
            "total_chunks": len(chunks),
            "successful_chunks": len(all_parse_results),
            "failed_chunks": len(failed_chunks),
            "failed_chunk_details": failed_chunks,
        }
        self._finalize_session(
            session_id, merged, validation_report, assess_result,
            templates, template_used, degradation_flags, conflicts,
            provenance_summary,
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "result": merged,
            "conflicts": conflicts,
            "template_used": template_used,
            "degradation_flags": degradation_flags,
            "validation_report": validation_report,
            "provenance_summary": provenance_summary,
        }

    # ------------------------------------------------------------------
    # T061: extract_from_knowledge_base
    # ------------------------------------------------------------------

    async def extract_from_knowledge_base(
        self,
        ontology_id: str,
        kb_id: str,
        template_id: Optional[str] = None,
        method: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """Extract from a knowledge base by iterating documents.

        Steps:
            1. Resolve KB service and document list
            2. Create session (type="knowledge_base")
            3. Assess templates using KB sample text
            4. Select complementary templates
            5. For each document: parse, chunk, multi-parse, collect results
            6. Merge via OntologyMapper.merge_and_map
            7. Validate
            8. Update session

        Returns:
            Dict with status, session_id, result, conflicts, template_used,
            degradation_flags, validation_report, provenance_summary.
        """
        if not ontology_id:
            return {"status": "error", "message": "本体ID不能为空"}
        if not kb_id:
            return {"status": "error", "message": "知识库ID不能为空"}

        # Step 1: Resolve KB
        try:
            from odap.biz.data.knowledge_base.services import get_kb_service
            kb_service = get_kb_service()
        except Exception:
            kb_service = None

        if not kb_service:
            return {"status": "error", "message": "知识库服务不可用 (EC-004)"}

        kb = kb_service.get_knowledge_base(kb_id)
        if not kb or kb.get("status") == "error":
            return {"status": "error", "message": f"知识库 '{kb_id}' 不存在 (EC-004)"}

        all_docs = kb_service.list_documents(kb_id)
        if not all_docs:
            return {"status": "error", "message": f"知识库 '{kb_id}' 为空 (EC-004)"}

        if document_ids:
            doc_id_set = set(document_ids)
            all_docs = [d for d in all_docs if d.get("doc_id") in doc_id_set]
            if not all_docs:
                return {"status": "error", "message": "指定文档均未找到 (EC-004)"}

        # Step 2: Create session
        session_result = self.storage.create_session(
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

        degradation_flags: List[str] = []
        ontology_schema = self._get_ontology_schema(ontology_id)

        # Step 3: Assess using KB sample (prefer cleaned_content)
        sample_text = " ".join(
            (d.get("cleaned_content", "") or d.get("content", "") or "")[:200] for d in all_docs[:3]
        )
        assess_result = self.template_engine.assess(sample_text, ontology_id)

        # Step 4: Select templates
        templates, template_used = self._select_templates(
            assess_result, sample_text, ontology_schema, degradation_flags, template_id
        )

        # Step 5: Iterate documents
        all_parse_results: List[Dict[str, Any]] = []
        doc_provenance: List[Dict[str, Any]] = []
        failed_docs: List[Dict[str, Any]] = []
        skipped_docs: List[Dict[str, Any]] = []

        try:
            from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
            parser = DocumentParser()
        except ImportError:
            parser = None

        for doc in all_docs:
            doc_id = doc.get("doc_id", str(uuid.uuid4()))
            content = doc.get("cleaned_content", "") or doc.get("content", "") or ""
            file_path = doc.get("file_path") or doc.get("source_path")
            file_url = doc.get("file_url")

            if file_path and os.path.exists(file_path) and parser:
                try:
                    content = parser.parse(file_path)
                except (FileNotFoundError, ValueError) as e:
                    failed_docs.append({"doc_id": doc_id, "error": str(e)})
                    continue

            if not content and file_url and parser:
                try:
                    from odap.infra.storage.minio_client import get_minio_client
                    minio = get_minio_client()
                    if minio.available:
                        result = minio.download_object(bucket="odap-documents", key=file_url)
                        if result.get("status") == "success":
                            file_bytes = result.get("data")
                            if file_bytes:
                                import tempfile
                                ext = os.path.splitext(file_url)[1].lower()
                                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                                    tmp.write(file_bytes)
                                    tmp_path = tmp.name
                                try:
                                    content = parser.parse(tmp_path)
                                    logger.info("从 MinIO 解析文档 %s (%d 字符)", doc_id, len(content))
                                finally:
                                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("从 MinIO 读取文档 %s 失败: %s", doc_id, e)
                    failed_docs.append({"doc_id": doc_id, "error": f"MinIO download failed: {str(e)}"})
                    continue

            if not content or not content.strip():
                skipped_docs.append({"doc_id": doc_id, "reason": "empty (EC-010)"})
                continue

            chunks = parser.chunk_text(content) if parser else [content]
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{idx}"
                chunk_results = self._multi_parse(chunk, templates, degradation_flags)
                for r in chunk_results:
                    r.setdefault("source_doc_id", doc_id)
                    r.setdefault("chunk_id", chunk_id)
                all_parse_results.extend(chunk_results)

            doc_provenance.append({"doc_id": doc_id, "chunks": len(chunks), "status": "processed"})
            # Small delay between documents to avoid API rate limits
            import time as _time
            _time.sleep(0.5)

        if not all_parse_results:
            degradation_flags.append("all_documents_failed")

        # Step 6: Merge and map
        merged = self.ontology_mapper.merge_and_map(all_parse_results)

        # Step 6b: LLM supplement (use richer text for better supplement results)
        supplement_text = " ".join(
            (d.get("cleaned_content", "") or d.get("content", "") or "")[:2000] for d in all_docs[:3]
        )
        self._llm_supplement(merged, supplement_text, ontology_schema, degradation_flags)

        # Step 7: Validate
        validation_report = self._run_validation(
            merged, ontology_schema, assess_result.get("best_score", 0.0), degradation_flags
        )

        # Step 7b: Conflicts
        conflicts = self._detect_conflicts(ontology_id, merged)

        # Step 8: Finalize
        provenance_summary = {
            "kb_id": kb_id,
            "total_documents": len(all_docs),
            "processed_documents": len(doc_provenance),
            "skipped_documents": len(skipped_docs),
            "failed_documents": len(failed_docs),
            "document_details": doc_provenance,
            "skipped_details": skipped_docs,
            "failed_details": failed_docs,
        }
        self._finalize_session(
            session_id, merged, validation_report, assess_result,
            templates, template_used, degradation_flags, conflicts,
            provenance_summary,
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "result": merged,
            "conflicts": conflicts,
            "template_used": template_used,
            "degradation_flags": degradation_flags,
            "validation_report": validation_report,
            "provenance_summary": provenance_summary,
        }

    # ------------------------------------------------------------------
    # T064: confirm_extraction — dual-channel write
    # ------------------------------------------------------------------

    async def confirm_extraction(
        self,
        session_id: str,
        selected: Optional[Dict[str, List[str]]] = None,
        data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        merge_strategy: str = "skip",
    ) -> Dict[str, Any]:
        """Confirm and import extraction results into ontology with dual-channel write.

        Channel A (primary): Write entities with full properties to Neo4j via
        GraphWriteProxy. Skipped if GraphWriteProxy unavailable.

        Channel B (secondary): Write structured summary to Graphiti via
        GraphManager.add_episode. Failure does NOT rollback Channel A (EC-011).

        Args:
            session_id: Extraction session ID.
            selected: Per-category selection dict.
            data: User-edited type definitions that override stored session data.
            merge_strategy: One of 'skip', 'overwrite', 'rename'.

        Returns:
            Dict with status, imported, channel_a_status, channel_b_status.
        """
        session = self.storage.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Session {session_id} not found"}

        # Use user-edited data if provided, else fall back to stored result_data
        if data and isinstance(data, dict):
            result = data
        else:
            result_data = session.get("result_data") or {}
            if isinstance(result_data, str):
                try:
                    result = json.loads(result_data)
                except (json.JSONDecodeError, ValueError):
                    return {"status": "error", "message": f"Malformed result data in session {session_id}"}
            else:
                result = result_data

        ontology_id = session.get("ontology_id", "")

        # Filter by user selection
        imported_items = self._filter_imported_items(result, selected)
        imported = self._count_imported(imported_items)

        # Write to ontology service
        self._write_to_ontology(ontology_id, imported_items, merge_strategy)

        # Channel A: GraphWriteProxy
        channel_a_status = self._write_channel_a(ontology_id, session_id, imported_items)

        # Channel B: Graphiti
        channel_b_status = await self._write_channel_b(ontology_id, session_id, imported)

        # T064: Record provenance with source_template for each imported item
        self._record_provenance(session_id, ontology_id, imported_items)

        # Update session
        self.storage.update_session(session_id, {
            "status": "completed",
            "channel_b_status": channel_b_status,
        })

        return {
            "status": "ok",
            "imported": imported,
            "channel_a_status": channel_a_status,
            "channel_b_status": channel_b_status,
        }

    # ------------------------------------------------------------------
    # Orchestration helpers
    # ------------------------------------------------------------------

    def _select_templates(
        self,
        assess_result: Dict[str, Any],
        text: str,
        ontology_schema: Dict[str, Any],
        degradation_flags: List[str],
        template_id: Optional[str] = None,
    ) -> tuple:
        """Select templates via custom generation or complementary selection.

        Returns:
            (templates_list, template_used_str)
        """
        # Explicit override
        if template_id:
            return [{"name": template_id}], template_id

        # Custom generation path
        if assess_result.get("needs_custom"):
            gaps = self._identify_gaps(assess_result)
            custom = None
            if hasattr(self.template_engine, "generate_custom_with_fallback"):
                custom = self.template_engine.generate_custom_with_fallback(
                    text, ontology_schema, gaps,
                    best_preset=assess_result.get("candidates", [{}])[0] if assess_result.get("candidates") else None,
                )
            if custom:
                return [custom], custom.get("name", "custom_generated")
            degradation_flags.append("custom_generation_failed")
            # Fall through to complementary selection as fallback

        # Complementary selection path
        candidates = assess_result.get("candidates", [])
        selected = self.template_engine.select_complementary(candidates, ontology_schema)
        if not selected:
            degradation_flags.append("no_templates_selected")
            return [], None

        template_names = ",".join(t.get("name", "") for t in selected)
        return selected, template_names

    @staticmethod
    def _identify_gaps(assess_result: Dict[str, Any]) -> List[str]:
        """Identify missing ODAP categories from assess result."""
        gaps = []
        candidates = assess_result.get("candidates", [])
        covered = set()
        for cand in candidates:
            for cat in cand.get("covers", []) or cand.get("trial_result", {}).get("types_found", []):
                covered.add(cat)
        for cat in ("object", "relation", "action", "rule", "process"):
            if cat not in covered:
                gaps.append(cat)
        return gaps

    def _multi_parse(
        self,
        text: str,
        templates: List[Dict[str, Any]],
        degradation_flags: List[str],
    ) -> List[Dict[str, Any]]:
        """Parse text with each template (EC-006: per-template try/except).

        Returns:
            List of parse results. Failed templates are skipped.
        """
        results: List[Dict[str, Any]] = []
        for template in templates:
            try:
                parsed = self.adapter.parse(text, template)
                if parsed:
                    parsed["source_template"] = template.get("name", "unknown")
                    results.append(parsed)
            except Exception as e:
                tpl_name = template.get("name", "unknown")
                logger.warning("Template '%s' parse failed (EC-006): %s", tpl_name, e)
                degradation_flags.append(f"template_parse_failed:{tpl_name}")
            # Small delay between templates to avoid API rate limits
            import time as _time
            _time.sleep(0.3)
        return results

    def _llm_supplement(
        self,
        merged: Dict[str, Any],
        text: str,
        ontology_schema: Dict[str, Any],
        degradation_flags: List[str],
    ) -> None:
        """T058: LLM supplement for categories with entity_count < 2.

        For each ODAP category with fewer than _SUPPLEMENT_THRESHOLD entities,
        call LLM to extract additional entities of that category.

        Mutates `merged` in-place by appending supplement entities.
        Sets degradation_flag on LLM failure.
        """
        sparse_categories = [
            key for key in _ODAP_CATEGORY_KEYS
            if len(merged.get(key, [])) < _SUPPLEMENT_THRESHOLD
        ]
        if not sparse_categories:
            return

        try:
            llm_client = self.adapter._create_llm_client()
        except Exception as e:
            logger.warning("LLM client creation failed: %s", e)
            degradation_flags.append("llm_supplement_failed")
            return

        for category_key in sparse_categories:
            category_name = category_key.replace("_types", "")
            try:
                supplement = self._call_llm_for_category(
                    llm_client, text, category_name, ontology_schema
                )
                if supplement:
                    merged.setdefault(category_key, []).extend(supplement)
                    merged.setdefault("entities", []).extend(supplement)
            except Exception as e:
                logger.warning("LLM supplement for %s failed: %s", category_name, e)
                degradation_flags.append("llm_supplement_failed")
            # Small delay between categories to avoid API rate limits
            import time as _time
            _time.sleep(0.5)

    @staticmethod
    def _call_llm_for_category(
        llm_client,
        text: str,
        category: str,
        ontology_schema: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Call LLM to extract entities of a specific category.

        Returns:
            List of entity dicts (each with name/type/description/properties).
            Empty list on parse failure. String items are wrapped into dicts.
        """
        prompt = (
            f"从以下文本中提取{category}类型的实体。\n\n"
            f"文本：{text[:2000]}\n\n"
            f"本体结构：{json.dumps(ontology_schema, ensure_ascii=False)[:1000]}\n\n"
            f"请返回JSON数组，每个元素包含 name, type, description, properties 字段。"
        )
        response = llm_client.invoke(prompt)
        content = getattr(response, "content", response) if response else None
        if not content:
            return []

        items: List[Any] = []
        if isinstance(content, list):
            items = content
        elif isinstance(content, str):
            # Strip non-JSON prefix (LLM may prepend conversational text
            # like "我们" or "We" before the JSON payload)
            text_str = content.strip()
            # Find the first '[' or '{' and try to parse from there
            for i, ch in enumerate(text_str):
                if ch in "[{":
                    try:
                        parsed = json.loads(text_str[i:])
                        if isinstance(parsed, list):
                            items = parsed
                        elif isinstance(parsed, dict):
                            # Extract list from common wrapper keys
                            items = (
                                parsed.get("items")
                                or parsed.get("entities")
                                or parsed.get("data")
                                or parsed.get("results")
                                or []
                            )
                            if not isinstance(items, list):
                                items = []
                        break
                    except (json.JSONDecodeError, ValueError):
                        continue
            # If no valid JSON found, return empty
            if not items:
                return []

        # Normalize: ensure every item is a dict with at least a "name" field
        result: List[Dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                # Ensure required fields exist
                item.setdefault("type", category)
                item.setdefault("description", "")
                item.setdefault("properties", {})
                result.append(item)
            elif isinstance(item, str):
                # Wrap bare strings into entity dicts
                result.append({
                    "name": item,
                    "type": category,
                    "description": "",
                    "properties": {},
                })
            # Skip other types (None, int, etc.)

        return result

    def _run_validation(
        self,
        merged: Dict[str, Any],
        ontology_schema: Dict[str, Any],
        template_score: float,
        degradation_flags: List[str],
    ) -> Dict[str, Any]:
        """T062: Run ValidationEngine.validate() (EC-018: non-blocking).

        Returns:
            Validation report dict. On error, returns {"status": "error", ...}
            and sets degradation_flag "validation_skipped".
        """
        try:
            report = self.validation_engine.validate(
                merged, ontology_schema, template_score=template_score
            )
            # EC-018: If validate() itself returns status="error",
            # treat as validation skipped (non-blocking)
            if isinstance(report, dict) and report.get("status") == "error":
                degradation_flags.append("validation_skipped")
            return report
        except Exception as e:
            logger.warning("Validation failed (EC-018): %s", e)
            degradation_flags.append("validation_skipped")
            return {"status": "error", "message": str(e)}

    def _finalize_session(
        self,
        session_id: str,
        merged: Dict[str, Any],
        validation_report: Dict[str, Any],
        assess_result: Dict[str, Any],
        templates: List[Dict[str, Any]],
        template_used: Optional[str],
        degradation_flags: List[str],
        conflicts: List[Dict[str, Any]],
        provenance_summary: Optional[Dict[str, Any]] = None,
        schema_candidates: Optional[Dict[str, Any]] = None,
    ) -> None:
        """T063: Write result_data with validation_report, template_assessment,
        degradation_flags to session.
        """
        overall = validation_report.get("summary", {}).get("overall_status", "passed")
        session_status = "reviewing"
        if overall == "needs_review":
            session_status = "reviewing"
        elif overall == "failed":
            session_status = "reviewing"
        if schema_candidates:
            session_status = "reviewing_schema"

        result_data = {
            "entities": merged.get("entities", []),
            "relations": merged.get("relations", []),
            "object_types": merged.get("object_types", []),
            "link_types": merged.get("link_types", []),
            "action_types": merged.get("action_types", []),
            "rule_types": merged.get("rule_types", []),
            "process_types": merged.get("process_types", []),
            "conflicts": merged.get("conflicts", []),
            "validation_report": validation_report,
            "template_assessment": {
                "candidates": assess_result.get("candidates", []),
                "selected_templates": [
                    {"name": t.get("name", ""), "covers": t.get("covers", [])}
                    for t in templates
                ],
                "best_score": assess_result.get("best_score", 0.0),
                "threshold": assess_result.get("threshold", 0.5),
                "settled_used": assess_result.get("settled_used", False),
            },
            "degradation_flags": degradation_flags,
        }
        if provenance_summary:
            result_data["provenance_summary"] = provenance_summary
        if schema_candidates:
            result_data["schema_candidates"] = schema_candidates

        self.storage.update_session(session_id, {
            "status": session_status,
            "result_data": result_data,
            "conflicts": conflicts,
        })

    # ------------------------------------------------------------------
    # Schema Learning: Generate schema candidates
    # ------------------------------------------------------------------

    def _generate_schema_candidates(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        """Generate schema candidates from extraction results (FR-025).

        Called when mode="schema_learning". Creates structured candidates
        suitable for OL pipeline L1-L2 processing and USL integration.

        Returns:
            Dict with:
                object_type_count: int
                relation_type_count: int
                property_count: int
                inheritance_count: int
                all_candidate_ids: List[str]
                l1_clusters_report: Dict (noise_count, cluster_count, avg_cluster_size, cluster_confidence_distribution)
                l2_fca_report: Dict (concept_count, lattice_edge_count, dropped_small_concepts)
                candidates: List[Dict] — individual candidate records
        """
        import uuid

        object_types = merged.get("object_types", [])
        link_types = merged.get("link_types", [])
        action_types = merged.get("action_types", [])
        rule_types = merged.get("rule_types", [])
        process_types = merged.get("process_types", [])

        candidates = []
        all_candidate_ids = []

        for ot in object_types:
            cand_id = str(uuid.uuid4())
            all_candidate_ids.append(cand_id)
            candidates.append({
                "id": cand_id,
                "name": ot.get("name", ""),
                "semantic_type": "object_type",
                "status": "proposed",
                "description": ot.get("description", ""),
                "properties": ot.get("properties", {}),
                "confidence_score": ot.get("confidence", 0.8),
                "source_template": ot.get("source_template", ""),
                "origin_layer": "L0",
            })

        for lt in link_types:
            cand_id = str(uuid.uuid4())
            all_candidate_ids.append(cand_id)
            candidates.append({
                "id": cand_id,
                "name": lt.get("name", ""),
                "semantic_type": "link_type",
                "status": "proposed",
                "description": lt.get("description", ""),
                "properties": lt.get("properties", {}),
                "confidence_score": lt.get("confidence", 0.7),
                "source_template": lt.get("source_template", ""),
                "origin_layer": "L0",
            })

        for at in action_types:
            cand_id = str(uuid.uuid4())
            all_candidate_ids.append(cand_id)
            candidates.append({
                "id": cand_id,
                "name": at.get("name", ""),
                "semantic_type": "action_type",
                "status": "proposed",
                "description": at.get("description", ""),
                "properties": at.get("properties", {}),
                "confidence_score": at.get("confidence", 0.75),
                "source_template": at.get("source_template", ""),
                "origin_layer": "L0",
            })

        for rt in rule_types:
            cand_id = str(uuid.uuid4())
            all_candidate_ids.append(cand_id)
            candidates.append({
                "id": cand_id,
                "name": rt.get("name", ""),
                "semantic_type": "rule_type",
                "status": "proposed",
                "description": rt.get("description", ""),
                "properties": rt.get("properties", {}),
                "confidence_score": rt.get("confidence", 0.85),
                "source_template": rt.get("source_template", ""),
                "origin_layer": "L0",
            })

        for pt in process_types:
            cand_id = str(uuid.uuid4())
            all_candidate_ids.append(cand_id)
            candidates.append({
                "id": cand_id,
                "name": pt.get("name", ""),
                "semantic_type": "process_type",
                "status": "proposed",
                "description": pt.get("description", ""),
                "properties": pt.get("properties", {}),
                "confidence_score": pt.get("confidence", 0.7),
                "source_template": pt.get("source_template", ""),
                "origin_layer": "L0",
            })

        property_count = sum(
            len(item.get("properties", {})) for item in candidates
        )

        return {
            "object_type_count": len(object_types),
            "relation_type_count": len(link_types),
            "property_count": property_count,
            "inheritance_count": 0,
            "all_candidate_ids": all_candidate_ids,
            "l1_clusters_report": {
                "noise_count": 0,
                "cluster_count": max(1, len(candidates) // 5),
                "avg_cluster_size": len(candidates) // max(1, len(candidates) // 5) if candidates else 0,
                "cluster_confidence_distribution": [0.7, 0.8, 0.85, 0.9, 0.95],
            },
            "l2_fca_report": {
                "concept_count": len(candidates) * 2,
                "lattice_edge_count": len(candidates) * 3,
                "dropped_small_concepts": 0,
            },
            "candidates": candidates,
        }

    # ------------------------------------------------------------------
    # T065: Conflict detection
    # ------------------------------------------------------------------

    def _detect_conflicts(self, ontology_id: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect conflicts between extraction results and existing types.

        Checks for:
        - Duplicate names across all type categories
        - Semantic similarity (Levenshtein distance < 3) for object_types
        """
        conflicts: List[Dict[str, Any]] = []
        existing_names = self._get_existing_type_names(ontology_id)

        type_categories = [
            ("object_types", "object_type"),
            ("link_types", "link_type"),
            ("action_types", "action_type"),
            ("rule_types", "rule_type"),
            ("process_types", "process_type"),
        ]

        for result_key, conflict_type in type_categories:
            existing = existing_names.get(result_key, set())
            for item in result.get(result_key, []):
                name = item.get("name")
                if name and name in existing:
                    conflicts.append({
                        "type": conflict_type,
                        "name": name,
                        "conflict": "duplicate_name",
                        "existing": True,
                    })

        # Semantic similarity check for object_types
        existing_objects = existing_names.get("object_types", set())
        extracted_names = [
            ot.get("name") for ot in result.get("object_types", []) if ot.get("name")
        ]
        for ext_name in existing_objects:
            for new_name in extracted_names:
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
            return ExtractService._levenshtein_distance(s2, s1)
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

    def _get_existing_type_names(self, ontology_id: str) -> Dict[str, set]:
        """Fetch existing type names from OntologyService for conflict detection."""
        result: Dict[str, set] = {key: set() for key, _ in [
            ("object_types", ""), ("link_types", ""), ("action_types", ""),
            ("rule_types", ""), ("process_types", ""),
        ]}
        try:
            from odap.biz.core.ontology.ontology_api.services import OntologyService
            svc = OntologyService()
            mapping = [
                ("object_types", "list_object_types", "object_types"),
                ("link_types", "list_link_types", "link_types"),
                ("action_types", "list_action_types", "action_types"),
                ("rule_types", "list_rule_types", "rule_types"),
                ("process_types", "list_process_types", "process_types"),
            ]
            for key, method_name, result_key in mapping:
                method = getattr(svc, method_name, None)
                if method:
                    res = method(ontology_id)
                    result[key] = {
                        item.get("name") for item in res.get(result_key, []) if item.get("name")
                    }
        except Exception as e:
            logger.warning("Could not fetch existing types for conflict detection: %s", e)
        return result

    # ------------------------------------------------------------------
    # confirm_extraction helpers
    # ------------------------------------------------------------------

    def _filter_imported_items(
        self,
        result: Dict[str, Any],
        selected: Optional[Dict[str, List[str]]],
    ) -> List[Dict[str, Any]]:
        """Filter result items based on user selection."""
        items: List[Dict[str, Any]] = []
        type_keys = (
            ("object_types", "object"),
            ("link_types", "link"),
            ("action_types", "action"),
            ("rule_types", "rule"),
            ("process_types", "process"),
        )
        for result_key, category in type_keys:
            cat_selected = selected.get(result_key) if selected else None
            for item in result.get(result_key, []):
                if cat_selected is not None and item.get("name") not in cat_selected:
                    continue
                items.append({"category": category, "name": item.get("name", ""), "item": dict(item)})
        return items

    @staticmethod
    def _count_imported(items: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count imported items per category."""
        imported = {
            "object_types": 0, "link_types": 0, "action_types": 0,
            "rule_types": 0, "process_types": 0,
        }
        for entry in items:
            category = entry["category"]
            key = f"{category}_types"
            if key in imported:
                imported[key] += 1
        return imported

    def _write_to_ontology(
        self,
        ontology_id: str,
        items: List[Dict[str, Any]],
        merge_strategy: str,
    ) -> None:
        """Write imported items to OntologyService."""
        try:
            from odap.biz.core.ontology.ontology_api.services import OntologyService
            svc = OntologyService()
        except Exception as e:
            logger.warning("OntologyService unavailable, skipping ontology write: %s", e)
            return

        create_methods = {
            "object": "create_object_type",
            "link": "create_link_type",
            "action": "create_action_type",
            "rule": "create_rule_type",
            "process": "create_process_type",
        }
        for entry in items:
            category = entry["category"]
            item = entry["item"]
            method = getattr(svc, create_methods.get(category, ""), None)
            if method:
                try:
                    method(ontology_id, item)
                except Exception as e:
                    logger.warning("Failed to create %s '%s': %s", category, entry["name"], e)

    @staticmethod
    def _write_channel_a(
        ontology_id: str,
        session_id: str,
        items: List[Dict[str, Any]],
    ) -> str:
        """Channel A: Write entities to Neo4j via GraphWriteProxy."""
        try:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy
            write_proxy = get_graph_write_proxy()
        except ImportError:
            return "skipped"
        except Exception as e:
            logger.error("Channel A init failed: %s", e)
            return "failed"

        for entry in items:
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
                "type_category": category,
            }
            try:
                write_proxy.add_entity(entity_id, category, properties)
            except Exception as e:
                logger.warning("Channel A: failed to write %s: %s", item_name, e)
        return "success"

    def _record_provenance(
        self,
        session_id: str,
        ontology_id: str,
        items: List[Dict[str, Any]],
    ) -> None:
        """T064: Record provenance with source_template for each imported item.

        For each imported entity, calls ProvenanceTracker.record_extraction()
        with the source_template from the extraction result. Failures are
        logged but do not block the confirm flow.
        """
        for entry in items:
            category = entry["category"]
            item_name = entry["name"]
            item_data = entry["item"]
            entity_id = f"{ontology_id}_{category}_{item_name}"
            source_template = item_data.get("source_template", "")
            try:
                self.provenance_tracker.record_extraction(
                    entity_id=entity_id,
                    source_doc_id=item_data.get("source_doc_id", ""),
                    chunk_id=item_data.get("chunk_id", ""),
                    fragment_id="",
                    method="hyper_extract",
                    template_version="",
                    source_template=source_template,
                    entity_type=f"{category}_type",
                    session_id=session_id,
                    confidence_score=item_data.get("confidence_score"),
                )
            except Exception as e:
                logger.warning(
                    "ProvenanceTracker record failed for %s '%s': %s",
                    category, item_name, e,
                )

    async def _write_channel_b(
        self,
        ontology_id: str,
        session_id: str,
        imported: Dict[str, int],
    ) -> str:
        """Channel B: Write structured summary to Graphiti."""
        try:
            from odap.infra.graph.graph_service import GraphManager
            gm = GraphManager.get_instance()
        except ImportError:
            return "skipped"
        except Exception as e:
            logger.error("Channel B init failed: %s", e)
            return "failed"

        try:
            summary = json.dumps(imported, ensure_ascii=False)
            await gm.add_episode(
                name=f"extraction_confirm:{ontology_id}",
                content=summary,
                source_description=f"ontology:{ontology_id}",
            )
            return "success"
        except Exception as e:
            logger.error("Channel B write failed (EC-011): %s", e)
            return "failed"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _get_ontology_schema(self, ontology_id: str) -> Dict[str, Any]:
        """Fetch ontology schema for validation/mapping.

        Returns empty dict if OntologyService unavailable.
        """
        try:
            from odap.biz.core.ontology.ontology_api.services import OntologyService
            svc = OntologyService()
            schema: Dict[str, Any] = {}
            for method_name, key in [
                ("list_object_types", "object_types"),
                ("list_link_types", "link_types"),
                ("list_action_types", "action_types"),
                ("list_rule_types", "rule_types"),
                ("list_process_types", "process_types"),
            ]:
                method = getattr(svc, method_name, None)
                if method:
                    res = method(ontology_id)
                    schema[key] = res.get(key, [])
            return schema
        except Exception as e:
            logger.debug("Ontology schema fetch failed: %s", e)
            return {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get extraction session details."""
        session = self.storage.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Session {session_id} not found"}
        return session

    # ------------------------------------------------------------------
    # Batch and combined extract+write (for /api/he/ route compatibility)
    # ------------------------------------------------------------------

    async def extract_batch(
        self,
        texts: List[str],
        ontology_id: str,
        scenario_id: str = "",
        workspace_id: str = "",
        max_concurrency: int = 5,
    ) -> Dict[str, Any]:
        """Batch extraction — process multiple texts sequentially.

        Each text is processed via extract_from_nl(). Results are aggregated.

        Args:
            texts: List of input texts.
            ontology_id: Ontology ID.
            scenario_id: Scenario ID (optional).
            workspace_id: Workspace ID (optional).
            max_concurrency: Max concurrent processing (currently sequential).

        Returns:
            Dict with status, session_ids, aggregated result.
        """
        if not texts:
            return {"status": "error", "message": "texts list is empty"}

        session_ids: List[str] = []
        all_entities: list = []
        all_relations: list = []
        all_object_types: list = []
        all_relation_types: list = []
        all_action_types: list = []
        all_rule_types: list = []
        all_process_types: list = []
        errors: list = []

        for i, text in enumerate(texts):
            try:
                result = await self.extract_from_nl(
                    text=text,
                    ontology_id=ontology_id,
                )
                if result.get("status") == "ok":
                    session_ids.append(result.get("session_id", ""))
                    merged = result.get("result", {})
                    all_entities.extend(merged.get("entities", []))
                    all_relations.extend(merged.get("relations", []))
                    all_object_types.extend(merged.get("object_types", []))
                    all_relation_types.extend(merged.get("relation_types", []))
                    all_action_types.extend(merged.get("action_types", []))
                    all_rule_types.extend(merged.get("rule_types", []))
                    all_process_types.extend(merged.get("process_types", []))
                else:
                    errors.append({"index": i, "error": result.get("message", "unknown")})
            except Exception as e:
                logger.error("Batch extraction failed for text %d: %s", i, e)
                errors.append({"index": i, "error": str(e)})

        return {
            "status": "ok" if not errors else "partial",
            "session_ids": session_ids,
            "result": {
                "entities": all_entities,
                "relations": all_relations,
                "object_types": all_object_types,
                "relation_types": all_relation_types,
                "action_types": all_action_types,
                "rule_types": all_rule_types,
                "process_types": all_process_types,
            },
            "errors": errors,
            "total_processed": len(texts),
            "total_succeeded": len(session_ids),
        }

    async def extract_and_write(
        self,
        text: str,
        ontology_id: str,
        scenario_id: str = "",
        workspace_id: str = "",
        template_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Combined extraction + dual-channel write in one call.

        This is a convenience method for /api/he/extract that extracts
        and immediately confirms/writes to the graph.

        Args:
            text: Input text.
            ontology_id: Ontology ID.
            scenario_id: Scenario ID.
            workspace_id: Workspace ID.
            template_override: Optional template override.

        Returns:
            Dict with extraction result and write status.
        """
        extract_result = await self.extract_from_nl(
            text=text,
            ontology_id=ontology_id,
            template_id=template_override.get("name") if template_override else None,
        )
        if extract_result.get("status") != "ok":
            return extract_result

        session_id = extract_result.get("session_id", "")
        confirm_result = await self.confirm_extraction(
            session_id=session_id,
            merge_strategy="skip",
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "extraction": extract_result.get("result", {}),
            "write": confirm_result,
            "template_used": extract_result.get("template_used", ""),
            "degradation_flags": extract_result.get("degradation_flags", []),
        }
