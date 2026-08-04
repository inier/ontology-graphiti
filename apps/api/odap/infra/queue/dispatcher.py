"""Iter 2.2: Task dispatcher — public API for enqueuing queue work.

This module provides the single entry point for all queue operations. Callers
should never use ``celery_app.send_task`` or ``task.delay`` directly — they
should go through ``dispatch_*`` functions here.

Public API:
    - dispatch_feed_he_kb(...)        — enqueue HE KA feeding
    - dispatch_map_to_ontology(...)   — enqueue ontology mapping
    - dispatch_process_multimodal(...) — enqueue multimodal processing
    - dispatch_ingestion_to_queue(...) — convenience wrapper for ingestion output

Graceful degradation:
    When celery is unavailable (``CELERY_AVAILABLE = False``), each dispatch
    function falls back to synchronous in-process execution and returns a
    ``DispatchResult`` with ``mode="sync"``. This keeps the module fully
    functional in test environments and when Redis is not running.

Design (ADR-074 §2.2):
    Three-tier priority routing:
        - high_priority: user-triggered, latency-sensitive (HITL, manual input)
        - normal:        regular ingestion (news scrape, file upload)
        - batch:         bulk/background (KB iteration, large document sets)
"""

import logging
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .queue_worker import (
    get_celery_app,
    CELERY_AVAILABLE,
    resolve_queue,
    QUEUE_HIGH_PRIORITY,
    QUEUE_NORMAL,
    QUEUE_BATCH,
)
from .tasks import (
    TASK_FEED_HE_KB,
    TASK_MAP_TO_ONTOLOGY,
    TASK_PROCESS_MULTIMODAL,
    feed_he_kb_impl,
    map_to_ontology_impl,
    process_multimodal_impl,
)

logger = logging.getLogger("queue_dispatcher")


# =====================================================================
# DispatchResult — uniform return type
# =====================================================================

@dataclass
class DispatchResult:
    """Result of a dispatch operation.

    Attributes:
        task_id: Celery task ID (async) or generated UUID (sync).
        mode: "async" if enqueued to celery, "sync" if executed in-process.
        queue: Queue name the task was routed to.
        status: "dispatched" (async), "completed" / "failed" (sync).
        result: Task output dict (only for sync mode).
        error: Error message if status is "failed".
        task_name: Registered celery task name.
    """

    task_id: str
    mode: str  # "async" | "sync"
    queue: str
    status: str  # "dispatched" | "completed" | "failed"
    task_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# Dispatch functions
# =====================================================================

def dispatch_feed_he_kb(
    workspace_id: str,
    ontology_id: str,
    text: str,
    template_id: Optional[str] = None,
    source_doc_id: Optional[str] = None,
    priority: Optional[str] = None,
) -> DispatchResult:
    """Enqueue a feed-to-KA task at the given priority.

    Args:
        workspace_id: Workspace for kb partitioning.
        ontology_id: Target ontology ID.
        text: Text to feed to the persistent HE Knowledge Abstract.
        template_id: Optional HE template path override.
        source_doc_id: Optional source document ID for traceability.
        priority: "high" / "normal" / "batch" (default: "normal").

    Returns:
        DispatchResult with task routing and status.
    """
    queue = resolve_queue(priority)

    if CELERY_AVAILABLE:
        app = get_celery_app()
        async_result = app.send_task(
            TASK_FEED_HE_KB,
            args=[workspace_id, ontology_id, text],
            kwargs={
                "template_id": template_id,
                "source_doc_id": source_doc_id,
            },
            queue=queue,
        )
        logger.info(
            "dispatch_feed_he_kb: async task=%s queue=%s ws=%s ont=%s",
            async_result.id, queue, workspace_id, ontology_id,
        )
        return DispatchResult(
            task_id=async_result.id,
            mode="async",
            queue=queue,
            status="dispatched",
            task_name=TASK_FEED_HE_KB,
        )

    # Synchronous fallback
    try:
        result = feed_he_kb_impl(
            workspace_id, ontology_id, text, template_id, source_doc_id
        )
        status = "completed" if result.get("status") in ("success", "skipped") else "failed"
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status=status,
            task_name=TASK_FEED_HE_KB,
            result=result,
            error=result.get("message") if status == "failed" else None,
        )
    except Exception as exc:
        logger.error("dispatch_feed_he_kb sync failed: %s", exc)
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status="failed",
            task_name=TASK_FEED_HE_KB,
            error=str(exc),
        )


def dispatch_map_to_ontology(
    workspace_id: str,
    ontology_id: str,
    extraction_session_id: Optional[str] = None,
    priority: Optional[str] = None,
) -> DispatchResult:
    """Enqueue a map-to-ontology task.

    Reads the accumulated KA state and maps it to the ODAP 5-class ontology
    schema.

    Args:
        workspace_id: Workspace for kb partitioning.
        ontology_id: Target ontology ID.
        extraction_session_id: Optional session ID for tracking.
        priority: "high" / "normal" / "batch" (default: "normal").

    Returns:
        DispatchResult with task routing and status.
    """
    queue = resolve_queue(priority)

    if CELERY_AVAILABLE:
        app = get_celery_app()
        async_result = app.send_task(
            TASK_MAP_TO_ONTOLOGY,
            args=[workspace_id, ontology_id],
            kwargs={"extraction_session_id": extraction_session_id},
            queue=queue,
        )
        logger.info(
            "dispatch_map_to_ontology: async task=%s queue=%s ws=%s ont=%s",
            async_result.id, queue, workspace_id, ontology_id,
        )
        return DispatchResult(
            task_id=async_result.id,
            mode="async",
            queue=queue,
            status="dispatched",
            task_name=TASK_MAP_TO_ONTOLOGY,
        )

    # Synchronous fallback
    try:
        result = map_to_ontology_impl(workspace_id, ontology_id, extraction_session_id)
        status = "completed" if result.get("status") == "success" else "failed"
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status=status,
            task_name=TASK_MAP_TO_ONTOLOGY,
            result=result,
            error=result.get("message") if status == "failed" else None,
        )
    except Exception as exc:
        logger.error("dispatch_map_to_ontology sync failed: %s", exc)
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status="failed",
            task_name=TASK_MAP_TO_ONTOLOGY,
            error=str(exc),
        )


def dispatch_process_multimodal(
    workspace_id: str,
    source_ref: str,
    mime_type: str,
    priority: Optional[str] = None,
    **kwargs: Any,
) -> DispatchResult:
    """Enqueue a multimodal processing task.

    Iter 4 (ADR-074 §4.1): Routes by MIME type to text/image/audio/video
    parsers. Currently only text/* is fully implemented; other modalities
    return a "not_implemented" status.

    Args:
        workspace_id: Workspace ID.
        source_ref: Reference to source data (MinIO key, URL, or inline text).
        mime_type: MIME type of the data.
        priority: "high" / "normal" / "batch" (default: "normal").
        **kwargs: Additional task arguments (ontology_id, template_id, etc.).

    Returns:
        DispatchResult with task routing and status.
    """
    queue = resolve_queue(priority)

    if CELERY_AVAILABLE:
        app = get_celery_app()
        async_result = app.send_task(
            TASK_PROCESS_MULTIMODAL,
            args=[workspace_id, source_ref, mime_type],
            kwargs=kwargs,
            queue=queue,
        )
        logger.info(
            "dispatch_process_multimodal: async task=%s queue=%s mime=%s",
            async_result.id, queue, mime_type,
        )
        return DispatchResult(
            task_id=async_result.id,
            mode="async",
            queue=queue,
            status="dispatched",
            task_name=TASK_PROCESS_MULTIMODAL,
        )

    # Synchronous fallback
    try:
        result = process_multimodal_impl(workspace_id, source_ref, mime_type, **kwargs)
        status = "completed" if result.get("status") in ("success", "skipped") else "failed"
        if result.get("status") == "not_implemented":
            status = "completed"  # not an error — just not yet supported
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status=status,
            task_name=TASK_PROCESS_MULTIMODAL,
            result=result,
            error=result.get("message") if status == "failed" else None,
        )
    except Exception as exc:
        logger.error("dispatch_process_multimodal sync failed: %s", exc)
        return DispatchResult(
            task_id=str(uuid.uuid4()),
            mode="sync",
            queue=queue,
            status="failed",
            task_name=TASK_PROCESS_MULTIMODAL,
            error=str(exc),
        )


def dispatch_ingestion_to_queue(
    workspace_id: str,
    ontology_id: str,
    text: str,
    source_doc_id: Optional[str] = None,
    template_id: Optional[str] = None,
    priority: Optional[str] = None,
) -> DispatchResult:
    """Convenience wrapper: dispatch a feed_he_kb task for ingestion output.

    This is the primary entry point for the data ingestion layer. After
    producing a pending-state OntologyDocument, the ingestion layer calls
    this function to enqueue the text for HE KA feeding.

    The default priority is "normal" (regular ingestion). For user-triggered
    manual input, pass priority="high". For bulk document iteration, pass
    priority="batch".

    Args:
        workspace_id: Workspace for kb partitioning.
        ontology_id: Target ontology ID.
        text: Combined/raw text from the ingestion output.
        source_doc_id: OntologyDocument.doc_id for traceability.
        template_id: Optional HE template path override.
        priority: "high" / "normal" / "batch" (default: "normal").

    Returns:
        DispatchResult from the underlying feed_he_kb dispatch.
    """
    if not priority:
        priority = "normal"

    logger.info(
        "dispatch_ingestion_to_queue: ws=%s ont=%s doc=%s priority=%s text_len=%d",
        workspace_id, ontology_id, source_doc_id, priority, len(text) if text else 0,
    )
    return dispatch_feed_he_kb(
        workspace_id=workspace_id,
        ontology_id=ontology_id,
        text=text,
        template_id=template_id,
        source_doc_id=source_doc_id,
        priority=priority,
    )
