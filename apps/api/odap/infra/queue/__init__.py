"""Iter 2.2: Data queue module — Celery + Redis three-tier priority queue.

Public API:
    - get_celery_app(): Returns the Celery app instance (or None if unavailable).
    - dispatch_feed_he_kb(workspace_id, ontology_id, text, ...): Enqueue a
      feed-to-kb task at the given priority.
    - dispatch_map_to_ontology(workspace_id, ontology_id, ...): Enqueue a
      map-to-ontology task.
    - dispatch_process_multimodal(...): Enqueue a multimodal processing task.

Queue tiers (plan 009 §2.2):
    - high_priority: user-triggered, latency-sensitive (e.g., manual input)
    - normal:        regular ingestion (e.g., news scrape, file upload)
    - batch:         bulk/background processing (e.g., KB document iteration)

Graceful degradation:
    When celery/redis are not installed or the broker is unreachable, tasks
    execute synchronously in-process (with a warning log). This keeps the
    module importable and testable without a running Redis broker.
"""

from .queue_worker import (
    get_celery_app,
    CELERY_AVAILABLE,
    QUEUE_HIGH_PRIORITY,
    QUEUE_NORMAL,
    QUEUE_BATCH,
)
from .dispatcher import (
    dispatch_feed_he_kb,
    dispatch_map_to_ontology,
    dispatch_process_multimodal,
    dispatch_ingestion_to_queue,
    DispatchResult,
)

__all__ = [
    "get_celery_app",
    "CELERY_AVAILABLE",
    "QUEUE_HIGH_PRIORITY",
    "QUEUE_NORMAL",
    "QUEUE_BATCH",
    "dispatch_feed_he_kb",
    "dispatch_map_to_ontology",
    "dispatch_process_multimodal",
    "dispatch_ingestion_to_queue",
    "DispatchResult",
]
