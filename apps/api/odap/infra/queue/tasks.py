"""Iter 2.2: Celery task definitions for the three-tier priority queue.

Task names (registered with the ``odap_queue`` Celery app):
    - ``odap_queue.feed_he_kb``        — feed text to the persistent HE KA
    - ``odap_queue.map_to_ontology``   — map accumulated KA state to ODAP ontology
    - ``odap_queue.process_multimodal`` — multimodal parsing via MultimodalRouter (Iter 4.1)

Design rules:
    - Each task is a *thin* wrapper around a ``_impl`` function. The impl does
      lazy imports of the service layer so that importing this module does not
      pull in heavy dependencies (hyperextract, langchain, etc.) at worker
      startup — only when the task actually runs.
    - All tasks return JSON-serializable dicts (celery json serializer).
    - When celery is not installed, the ``_impl`` functions are still callable
      directly by the dispatcher's synchronous fallback.

AGENTS.md compliance:
    - Service layer returns Dict[str, Any], never raises HTTPException.
    - Errors are caught and returned as {"status": "error", ...} dicts.
"""

import logging
import traceback
from typing import Any, Dict, Optional

from .queue_worker import get_celery_app, CELERY_AVAILABLE

logger = logging.getLogger("queue_tasks")

# Task name constants (used by dispatcher for send_task)
TASK_FEED_HE_KB = "odap_queue.feed_he_kb"
TASK_MAP_TO_ONTOLOGY = "odap_queue.map_to_ontology"
TASK_PROCESS_MULTIMODAL = "odap_queue.process_multimodal"


# =====================================================================
# Implementation functions (callable directly or via celery)
# =====================================================================

def feed_he_kb_impl(
    workspace_id: str,
    ontology_id: str,
    text: str,
    template_id: Optional[str] = None,
    source_doc_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Feed text to the persistent HE Knowledge Abstract.

    Iter 2.1 (ADR-074): Uses ``HEAdapter.feed_to_kb`` which calls HE's native
    ``Template.create`` + ``ka.load`` + ``ka.feed_text`` + ``ka.dump`` for
    incremental evolution.

    Args:
        workspace_id: Workspace for kb partitioning.
        ontology_id: Target ontology ID.
        text: Text to feed to the KA.
        template_id: Optional HE template path override.
        source_doc_id: Optional source document ID for traceability.

    Returns:
        Dict with status, kb_path, text_length, source_doc_id.
    """
    if not text or not text.strip():
        return {
            "status": "skipped",
            "message": "empty text, nothing to feed",
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }

    try:
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter, get_kb_path

        adapter = HEAdapter()
        if not adapter.is_available():
            return {
                "status": "error",
                "message": "hyperextract 未安装或不可用",
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
            }

        kb_path = get_kb_path(workspace_id, ontology_id)
        template_config: Optional[Dict[str, Any]] = None
        if template_id:
            template_config = {"template_path": template_id, "language": "zh"}

        ok = adapter.feed_to_kb(kb_path, text, template=template_config)
        if ok:
            logger.info(
                "feed_he_kb succeeded: ws=%s ont=%s chars=%d doc=%s",
                workspace_id, ontology_id, len(text), source_doc_id,
            )
            return {
                "status": "success",
                "kb_path": kb_path,
                "text_length": len(text),
                "template_id": template_id,
                "source_doc_id": source_doc_id,
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
            }
        else:
            return {
                "status": "error",
                "message": "feed_to_kb returned False (check adapter logs)",
                "kb_path": kb_path,
                "source_doc_id": source_doc_id,
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
            }
    except Exception as exc:
        logger.error("feed_he_kb failed: %s\n%s", exc, traceback.format_exc())
        return {
            "status": "error",
            "message": str(exc),
            "source_doc_id": source_doc_id,
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }


def map_to_ontology_impl(
    workspace_id: str,
    ontology_id: str,
    extraction_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Map accumulated KA state to the ODAP 5-class ontology schema.

    Reads the persistent KA via ``HEAdapter.load_from_kb`` and maps the
    accumulated entities/relations to ODAP object_types, link_types,
    action_types, rule_types, process_types via ``OntologyMapper``.

    Args:
        workspace_id: Workspace for kb partitioning.
        ontology_id: Target ontology ID.
        extraction_session_id: Optional session ID for tracking.

    Returns:
        Dict with status, kb_path, entity_count, relation_count, mapped_classes.
    """
    try:
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter, get_kb_path

        adapter = HEAdapter()
        if not adapter.is_available():
            return {
                "status": "error",
                "message": "hyperextract 未安装或不可用",
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
            }

        kb_path = get_kb_path(workspace_id, ontology_id)
        accumulated = adapter.load_from_kb(kb_path)
        if not accumulated:
            return {
                "status": "error",
                "message": f"KA not found or empty at {kb_path}",
                "kb_path": kb_path,
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
            }

        entities = accumulated.get("entities", [])
        relations = accumulated.get("relations", [])

        # Map to ODAP 5 classes
        from odap.biz.data.hyper_extract.impl.ontology_mapper import OntologyMapper
        mapper = OntologyMapper()
        mapped = mapper.map_to_odap_schema(entities, relations)

        logger.info(
            "map_to_ontology: ws=%s ont=%s entities=%d relations=%d",
            workspace_id, ontology_id, len(entities), len(relations),
        )
        return {
            "status": "success",
            "kb_path": kb_path,
            "entity_count": len(entities),
            "relation_count": len(relations),
            "mapped_classes": {
                "object_types": len(mapped.get("object_types", [])),
                "link_types": len(mapped.get("link_types", [])),
                "action_types": len(mapped.get("action_types", [])),
                "rule_types": len(mapped.get("rule_types", [])),
                "process_types": len(mapped.get("process_types", [])),
            },
            "extraction_session_id": extraction_session_id,
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }
    except Exception as exc:
        logger.error("map_to_ontology failed: %s\n%s", exc, traceback.format_exc())
        return {
            "status": "error",
            "message": str(exc),
            "extraction_session_id": extraction_session_id,
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }


def process_multimodal_impl(
    workspace_id: str,
    source_ref: str,
    mime_type: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Process multimodal data (text/image/audio/video) via MultimodalRouter.

    Iter 4.1 (ADR-074 §4.1): Routes by MIME type to the appropriate parser,
    then feeds the aggregated text to HE KA. Text modalities short-circuit
    directly to feed_he_kb (no parsing needed). Image/audio/video are parsed
    to text first, then fed to HE.

    Args:
        workspace_id: Workspace ID.
        source_ref: Reference to the source data (text content / file:/// path /
            base64 / minio:// reference).
        mime_type: MIME type of the data (e.g., "text/plain", "image/png",
            "audio/wav", "video/mp4").
        **kwargs: Additional arguments (ontology_id, template_id, source_doc_id).

    Returns:
        Dict with status, extracted text, modality info, and HE feed result.
    """
    if not mime_type:
        return {
            "status": "error",
            "message": "mime_type is required",
            "workspace_id": workspace_id,
            "source_ref": source_ref,
        }

    mime_lower = mime_type.lower()

    # Text modality — short-circuit directly to feed_he_kb (no parsing needed)
    if mime_lower.startswith("text/"):
        ontology_id = kwargs.get("ontology_id", "default")
        text = kwargs.get("text", "")
        if not text and source_ref:
            text = source_ref
        return feed_he_kb_impl(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            text=text,
            template_id=kwargs.get("template_id"),
            source_doc_id=kwargs.get("source_doc_id"),
        )

    # Image / Audio / Video — route via MultimodalRouter (Iter 4.1)
    try:
        from odap.infra.data_pipeline.multimodal_router import (
            get_multimodal_router,
            get_result_aggregator,
        )
        router = get_multimodal_router()
        aggregator = get_result_aggregator()

        parsed = router.route(mime_lower, source_ref)

        # 归集为统一文本
        aggregated = aggregator.aggregate([parsed])

        # C2 修复：全降级时不喂 HE KA（避免占位文本污染知识库）
        if aggregated.all_fallback or not aggregated.combined_text:
            return {
                "status": "error",
                "message": (
                    f"Modality '{mime_type}' 解析全部降级或无文本产出，"
                    f"跳过 HE 喂入避免污染知识库"
                ),
                "workspace_id": workspace_id,
                "source_ref": source_ref,
                "mime_type": mime_type,
                "modality": parsed.modality,
                "fallback": True,
            }

        # 将解析出的文本喂给 HE KA
        ontology_id = kwargs.get("ontology_id", "default")
        feed_result = feed_he_kb_impl(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            text=aggregated.combined_text,
            template_id=kwargs.get("template_id"),
            source_doc_id=kwargs.get("source_doc_id"),
        )

        return {
            "status": "success",
            "workspace_id": workspace_id,
            "source_ref": source_ref,
            "mime_type": mime_type,
            "modality": parsed.modality,
            "model_used": parsed.model_used,
            "confidence": parsed.confidence,
            "fallback": parsed.fallback,
            "extracted_text_length": len(aggregated.combined_text),
            "feed_result": feed_result,
        }
    except Exception as exc:
        logger.exception("process_multimodal failed for %s", mime_type)
        return {
            "status": "error",
            "message": str(exc),
            "workspace_id": workspace_id,
            "source_ref": source_ref,
            "mime_type": mime_type,
        }


# =====================================================================
# Celery task registration (only when celery is available)
# =====================================================================

if CELERY_AVAILABLE:
    _app = get_celery_app()

    @_app.task(name=TASK_FEED_HE_KB)
    def feed_he_kb_task(
        workspace_id: str,
        ontology_id: str,
        text: str,
        template_id: Optional[str] = None,
        source_doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Celery task wrapper for feed_he_kb_impl."""
        return feed_he_kb_impl(
            workspace_id, ontology_id, text, template_id, source_doc_id
        )

    @_app.task(name=TASK_MAP_TO_ONTOLOGY)
    def map_to_ontology_task(
        workspace_id: str,
        ontology_id: str,
        extraction_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Celery task wrapper for map_to_ontology_impl."""
        return map_to_ontology_impl(workspace_id, ontology_id, extraction_session_id)

    @_app.task(name=TASK_PROCESS_MULTIMODAL)
    def process_multimodal_task(
        workspace_id: str,
        source_ref: str,
        mime_type: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Celery task wrapper for process_multimodal_impl."""
        return process_multimodal_impl(workspace_id, source_ref, mime_type, **kwargs)

else:
    # Synchronous fallback: define plain functions so dispatcher can call
    # them directly without celery.
    def feed_he_kb_task(  # type: ignore[no-redef]
        workspace_id: str,
        ontology_id: str,
        text: str,
        template_id: Optional[str] = None,
        source_doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return feed_he_kb_impl(
            workspace_id, ontology_id, text, template_id, source_doc_id
        )

    def map_to_ontology_task(  # type: ignore[no-redef]
        workspace_id: str,
        ontology_id: str,
        extraction_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return map_to_ontology_impl(workspace_id, ontology_id, extraction_session_id)

    def process_multimodal_task(  # type: ignore[no-redef]
        workspace_id: str,
        source_ref: str,
        mime_type: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return process_multimodal_impl(workspace_id, source_ref, mime_type, **kwargs)
